"""
minimax_client.py — V0.7 MiniMax 云端模型客户端
实现 ILLMClient 接口，包装现有的 LLMClient
"""

import asyncio
import logging
import os
import time
from typing import Optional

from ..interfaces import ILLMClient, LLMResponse

logger = logging.getLogger(__name__)

# MiniMax M2.7 价格
PRICE_PER_1K_INPUT = 0.01
PRICE_PER_1K_OUTPUT = 0.03


class MiniMaxClient(ILLMClient):
    """
    MiniMax 云端模型客户端
    实现 ILLMClient 接口，包装现有的 LLMClient
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.minimaxi.com/anthropic"):
        self._api_key = api_key or os.environ.get(
            "MINIMAX_API_KEY",
            os.environ.get("ANTHROPIC_API_KEY")
        )
        self._base_url = base_url
        self._usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "call_count": 0,
        }
        self._cloud_available: Optional[bool] = None

    @property
    def usage(self) -> dict:
        return self._usage

    async def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        purpose: str = "general"
    ) -> LLMResponse:
        """
        通过云端 MiniMax M2.7 生成回复
        """
        start_time = time.time()

        # 检测云端是否可用
        if self._cloud_available is False:
            return LLMResponse(
                content="",
                model="cloud",
                tokens_used=0,
                latency_ms=(time.time() - start_time) * 1000,
                success=False,
                error="云端服务不可用",
            )

        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=self._api_key, base_url=self._base_url)

        full_messages = list(messages)

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

            # 更新 usage
            if hasattr(resp, "usage") and resp.usage:
                u = resp.usage
                self._usage["total_input_tokens"] += u.input_tokens
                self._usage["total_output_tokens"] += u.output_tokens
                cost = (u.input_tokens / 1000) * PRICE_PER_1K_INPUT + (u.output_tokens / 1000) * PRICE_PER_1K_OUTPUT
                self._usage["total_cost"] += cost

            self._usage["call_count"] += 1
            latency_ms = (time.time() - start_time) * 1000
            logger.debug(f"[MiniMax] out={self._usage.get('total_output_tokens', 0)} tokens | latency={latency_ms:.0f}ms | cost=${cost:.4f} | purpose={purpose}")

            self._cloud_available = True
            return LLMResponse(
                content=result if result else text,
                model="cloud",
                tokens_used=self._usage.get("total_output_tokens", 0),
                latency_ms=latency_ms,
                success=True,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"[MiniMax] 云端服务失败: {e}")
            self._cloud_available = False

            return LLMResponse(
                content="",
                model="cloud",
                tokens_used=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )
        finally:
            await client.close()

    async def embed(self, text: str) -> list[float]:
        """MiniMax 客户端目前不直接提供 embed 接口，返回占位向量"""
        logger.debug("[MiniMax] embed 调用跳过（使用 bge-m3）")
        return [0.0] * 1024

    def get_model_name(self) -> str:
        return "MiniMax-M2.7"

    async def health_check(self) -> bool:
        """健康检查：检测云端 LLM 是否可用"""
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
            return True
        except Exception as e:
            logger.warning(f"[MiniMax] 健康检查失败: {e}")
            self._cloud_available = False
            return False