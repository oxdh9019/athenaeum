"""
llm_gateway.py — V0.2 专用 LLM 调用封装
使用 anthropic SDK 调用 MiniMax-M2.7 模型
默认配置: ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

from anthropic import AsyncAnthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

PRICE_PER_1K_INPUT_TOKENS = 0.01
PRICE_PER_1K_OUTPUT_TOKENS = 0.03
MAX_TOKENS_PER_CALL = 2000

DEFAULT_API_KEY = "sk-cp-xRi9wdqgOnto2GQ06BfsB3dzXUM6oIBb5lIrPHSsphk6B5ECSv6WtsEaTcuO60onEgg8i9liZW7ORFSOKdx_mu__Mnw6AuMXwdeokshkBR_MgpM4hKa_54s"


@dataclass
class TokenUsage:
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
    V0.2 专用 LLM 调用网关
    """

    def __init__(
        self,
        model: str = "MiniMax-M2.7",
        api_key: Optional[str] = None,
        base_url: str = "https://api.minimaxi.com/anthropic",
    ):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY") or DEFAULT_API_KEY
        self._client = AsyncAnthropic(api_key=key, base_url=base_url)
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
        json_mode: bool = False,
    ) -> str:
        """
        发送对话请求到 LLM。

        参数:
            messages: 对话历史 [{"role": "user/assistant", "content": "..."}]
            system: 系统提示（可选）
            temperature: 温度参数
            max_tokens: 最大输出 Token 数
            json_mode: 是否要求 JSON 输出

        返回:
            LLM 回复文本
        """
        try:
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

            thinking = ""
            text = ""
            for block in response.content:
                if block.type == "thinking":
                    thinking = block.thinking
                elif block.type == "text":
                    text = block.text

            result = ""
            if thinking:
                result += f"[THINK]{thinking}[/THINK]"
            if text:
                result += f"[SPEAK]{text}[/SPEAK]"

            if hasattr(response, 'usage') and response.usage:
                usage = response.usage
                self._usage.add(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                )
                logger.debug(f"LLM调用: input={usage.input_tokens} output={usage.output_tokens}")

            return result if result else text

        except Exception as e:
            logger.error(f"LLM 调用错误: {str(e)}", exc_info=True)
            raise

    async def close(self):
        logger.info("LLM Gateway 连接已关闭")