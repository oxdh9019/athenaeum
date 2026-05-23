"""
LLM Gateway — API 调用封装，遵循 ADR-006 成本控制
使用 anthropic SDK 调用 MiniMax-M2.7 模型
配置: export ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
配置: export ANTHROPIC_API_KEY=your_api_key
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Token 价格（参考值，实际以账单为准）
PRICE_PER_1K_INPUT_TOKENS = 0.01   # $ / 1K tokens
PRICE_PER_1K_OUTPUT_TOKENS = 0.03  # $ / 1K tokens

# 单次调用上限
MAX_TOKENS_PER_CALL = 2000


@dataclass
class TokenUsage:
    """追踪 Token 消耗"""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0

    def add(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1
        cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS + \
               (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        self.total_cost += cost

    def summary(self) -> str:
        return (
            f"调用次数: {self.call_count} | "
            f"输入Token: {self.total_input_tokens} | "
            f"输出Token: {self.total_output_tokens} | "
            f"累计成本: ${self.total_cost:.4f}"
        )


class LLMGateway:
    """
    统一 LLM 调用网关。

    职责：
    - 封装 API 调用（使用 anthropic SDK 调用 MiniMax-M2.7）
    - 记录 Token 消耗
    - 超出上限时截断记忆（由调用方负责）
    """

    def __init__(self, model: str = "MiniMax-M2.7"):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

        if not api_key:
            logger.error("环境变量 ANTHROPIC_API_KEY 未设置")
            raise ValueError("环境变量 ANTHROPIC_API_KEY 未设置")

        # 延迟导入 anthropic
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = model
        self._usage = TokenUsage()
        logger.info(f"LLM Gateway 初始化完成，模型: {model}，API地址: {base_url}")

    @property
    def usage(self) -> TokenUsage:
        return self._usage

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_PER_CALL,
    ) -> str:
        """
        发送对话请求到 LLM。

        参数:
            messages: 对话历史 [{"role": "user/assistant", "content": "..."}]
            system: 系统提示（可选）
            temperature: 温度参数
            max_tokens: 最大输出 Token 数

        返回:
            LLM 回复文本（包含 [THINK] 和 标签）
        """
        try:
            # 转换消息格式为 anthropic 格式
            anthropic_messages = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    anthropic_messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": content}]
                    })
                elif role == "assistant":
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": [{"type": "text", "text": content}]
                    })

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system or "",
                messages=anthropic_messages,
                temperature=temperature,
            )

            # 解析响应
            thinking = ""
            text = ""
            for block in response.content:
                if block.type == "thinking":
                    thinking = block.thinking
                elif block.type == "text":
                    text = block.text

            # 组合成 [THINK]...[/THINK]...[/SPEAK] 格式
            result = ""
            if thinking:
                result += f"[THINK]{thinking}[/THINK]"
            if text:
                result += f"[SPEAK]{text}[/SPEAK]"

            # 记录 Token 使用（anthropic 返回 usage 字段）
            if hasattr(response, 'usage'):
                usage = response.usage
                self._usage.add(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                )
                cost = (usage.input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS + \
                       (usage.output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
                logger.debug(f"LLM调用: input={usage.input_tokens} output={usage.output_tokens} "
                            f"cost=${cost:.4f} | 累计: {self._usage.summary()}")

            return result

        except Exception as e:
            logger.error(f"LLM 调用错误: {str(e)}", exc_info=True)
            raise

    async def close(self):
        """关闭客户端连接"""
        logger.info("LLM Gateway 连接已关闭")