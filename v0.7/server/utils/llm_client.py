"""
llm_client.py — V0.3 LLM 客户端实现
使用 anthropic SDK 调用 MiniMax-M2.7 模型

【为什么是 anthropic SDK + MiniMax 域名？】
历史背景：v0.3 时期 MiniMax 官方 SDK 不稳定且无 Python async 客户端，
v0.3 选择"复用 anthropic 官方 SDK + 改 base_url"的方式接入 MiniMax 的
Anthropic 兼容端点，base_url 默认值是 `https://api.minimaxi.com/anthropic`。
这是 v0.3 的临时 hack，从 v0.4 起被 ADR-006 收编为标准做法：所有云端 LLM
调用统一走 `LLMGateway`（位于 utils/llm_gateway.py），本类仅作底层 adapter。
不要在业务代码中直接 new LLMClient()，请使用 `LLMGateway.choose()`。
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

PRICE_PER_1K_INPUT = 0.01
PRICE_PER_1K_OUTPUT = 0.03

# 简单脱敏：把异常的字符串里形如 `sk-xxx`、`sk-or-xxx`、`key=xxx`、`token=xxx`、
# `apikey=xxx` 的子串替换为 `<redacted>`，避免错误回显泄露密钥。
import re as _re
_SECRET_RE = _re.compile(
    r"(?i)(sk-[A-Za-z0-9_\-]{4,})|(api[_-]?key\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{6,})|(token\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{6,})"
)


def _redact_secrets(s: str) -> str:
    return _SECRET_RE.sub("<redacted>", s)


class LLMClient:
    """
    MiniMax-M2.7 LLM 客户端（兼容 v0.2）
    支持 fallback 到本地 Ollama
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.minimaxi.com/anthropic", fallback_llm=None):
        self._api_key = api_key or os.environ.get(
            "MINIMAX_API_KEY",
            os.environ.get("ANTHROPIC_API_KEY")
        )
        self._base_url = base_url
        self._fallback_llm = fallback_llm  # 备用本地 LLM（如 Ollama）
        self._usage = {"total_input_tokens": 0, "total_output_tokens": 0, "total_cost": 0.0}
        self._first_fallback_warning = True
        self._cloud_available = None  # None=未检测, True=可用, False=不可用
        self._checked = False
        self._router = None  # 可选：ModelRouter 实例（用于成本统计）

    def set_router(self, router) -> None:
        """注入 ModelRouter 用于成本统计。失败时静默忽略。"""
        self._router = router

    def _record_call(self, model: str, tokens: int, cost: float) -> None:
        if self._router is None:
            return
        try:
            self._router.record_call(model, tokens, cost)
        except Exception as e:
            logger.debug(f"[LLM] router.record_call 失败: {e}")

    async def health_check(self) -> bool:
        """启动时检测云端 LLM 是否可用"""
        if self._checked:
            return self._cloud_available
        
        if not self._api_key:
            logger.info("[LLM] 无 API Key，跳过云端健康检查")
            self._cloud_available = False
            self._checked = True
            return False
        
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self._api_key, base_url=self._base_url)
            resp = await client.messages.create(
                model="MiniMax-M2.7",
                max_tokens=10,
                system="test",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7,
            )
            await client.close()
            self._cloud_available = True
            logger.info("[LLM] 云端 LLM 健康检查通过")
            return True
        except Exception as e:
            await client.close() if 'client' in dir() else None
            logger.warning(f"[LLM] 云端 LLM 健康检查失败: {e}")
            self._cloud_available = False
            self._checked = True
            return False

    async def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        # 如果已检测到云端不可用，直接使用 fallback
        if self._cloud_available is False:
            if self._fallback_llm:
                return await self._fallback_llm.chat(messages, system, temperature, max_tokens)
            return self._get_fallback_response(messages)
        
        # 如果未检测，先做健康检查
        if self._cloud_available is None and not self._checked:
            await self.health_check()
        
        # 云端不可用，直接用 fallback
        if self._cloud_available is False:
            if self._fallback_llm:
                logger.info("[LLM] 使用本地 Ollama（云端不可用）")
                return await self._fallback_llm.chat(messages, system, temperature, max_tokens)
            return self._get_fallback_response(messages)
        
        # 云端可用，尝试调用
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=self._api_key, base_url=self._base_url)

        full_messages = []
        full_messages.extend(messages)

        try:
            resp = await client.messages.create(
                model="MiniMax-M2.7",
                max_tokens=max_tokens,
                system=system or "",
                messages=full_messages,
                temperature=temperature,
            )

            text = ""
            thinking = ""
            for block in resp.content:
                if block.type == "thinking":
                    thinking = block.thinking
                elif block.type == "text":
                    text = block.text

            result = ""
            if thinking:
                result += f"[THINK]{thinking}[/THINK]"
            if text:
                result += f"[SPEAK]{text}[/SPEAK]"

            if hasattr(resp, "usage") and resp.usage:
                u = resp.usage
                self._usage["total_input_tokens"] += u.input_tokens
                self._usage["total_output_tokens"] += u.output_tokens
                cost = (u.input_tokens / 1000) * PRICE_PER_1K_INPUT + (u.output_tokens / 1000) * PRICE_PER_1K_OUTPUT
                self._usage["total_cost"] += cost
                self._record_call("cloud", u.input_tokens + u.output_tokens, cost)
            else:
                self._record_call("cloud", 0, 0.0)

            return result if result else text

        except Exception as e:
            # 云端失败，标记并回退到本地 Ollama
            if self._fallback_llm:
                # 防泄漏：异常信息可能含 base_url/api_key 头几位的回显，统一脱敏
                safe_err = _redact_secrets(str(e))
                logger.warning(f"[LLM] 云端服务失败，切换到本地 Ollama: {safe_err}")
                self._cloud_available = False
                try:
                    return await self._fallback_llm.chat(messages, system, temperature, max_tokens)
                except Exception as fallback_e:
                    logger.error(f"[LLM] 本地 Ollama 也失败了: {fallback_e}")
            
            # 最后回退到 mock 数据
            logger.error(f"LLM chat failed: {e}")
            if self._fallback_llm:
                logger.error(f"[LLM] 本地 Ollama 也失败了: {fallback_e if 'fallback_e' in dir() else 'unknown'}")
            raise  # 不再回退到 mock 数据，直接抛出异常
        finally:
            await client.close()

    def _get_fallback_response(self, messages: list[dict]) -> str:
        import random
        
        greetings = [
            "你好！今天天气真不错呢。",
            "很高兴见到你，最近忙什么呢？",
            "你好呀！有什么新鲜事吗？",
            "嗨！好久不见了。",
            "您好！最近过得怎么样？",
        ]
        
        responses = [
            "我明白了，确实挺有意思的。",
            "好的，没问题，我也这么觉得。",
            "我理解你的意思，这很有道理。",
            "有意思，我之前也这么想过。",
            "我想想...你说得对。",
            "嗯，我知道了，继续说说吧。",
            "可以的，我觉得可行。",
            "当然可以，为什么不呢？",
            "好主意！我们试试看。",
            "我同意，这是个好想法。",
            "真的吗？说来听听。",
            "原来是这样，我明白了。",
            "挺有趣的，然后呢？",
            "我也这么觉得，太棒了。",
            "有意思，继续说。",
        ]
        
        questions = [
            "你呢？最近怎么样？",
            "你觉得呢？有什么建议吗？",
            "你怎么看这件事？",
            "有什么想法吗？我很想听。",
            "你想说什么？我在听。",
            "你觉得接下来会发生什么？",
            "你有什么计划吗？",
            "你对这件事怎么看？",
        ]
        
        opinions = [
            "我觉得这个想法很不错。",
            "这听起来很有意思。",
            "我认为这是对的。",
            "确实值得考虑。",
            "这让我想起了以前的事。",
            "有意思，我从没这么想过。",
            "我同意你的看法。",
            "这很有道理。",
        ]
        
        farewells = [
            "再见！改天再聊。",
            "下次见！祝你好运。",
            "祝你愉快！期待下次见面。",
            "拜拜！有空再聊。",
        ]
        
        content = ""
        for msg in messages:
            if msg.get("content"):
                content += msg["content"]
        
        if any(word in content for word in ["你好", "嗨", "Hello", "Hi", "初次见面"]):
            return random.choice(greetings)
        elif any(word in content for word in ["再见", "拜拜", "Goodbye", "先走了"]):
            return random.choice(farewells)
        elif any(word in content for word in ["？", "?", "什么", "怎么", "为什么", "吗"]):
            return random.choice(responses) + " " + random.choice(questions)
        else:
            return random.choice(opinions) + " " + random.choice(questions)

    async def embed(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        # 嵌入功能暂用 placeholder
        return [[0.0] * 1536 for _ in texts]

    async def close(self) -> None:
        pass

    @property
    def usage(self) -> dict:
        return self._usage
