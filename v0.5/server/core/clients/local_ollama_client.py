"""
local_ollama_client.py — V0.7 本地 Ollama 模型客户端
实现 ILLMClient 接口，包装现有的 OllamaLLMClient
"""

import asyncio
import json
import logging
import time
import urllib.request
from typing import Optional
from dataclasses import dataclass

from ..interfaces import ILLMClient, LLMResponse

logger = logging.getLogger(__name__)

# 本地模型价格（无费用，但用于统计）
LOCAL_COST_PER_1K_TOKENS = 0.0


@dataclass
class LocalModelConfig:
    """本地模型配置"""
    model: str = "qwen3.5:4b"
    base_url: str = "http://localhost:11434"
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    timeout: int = 300


class LocalOllamaClient(ILLMClient):
    """
    本地 Ollama 模型客户端
    实现 ILLMClient 接口，包装现有的 OllamaLLMClient
    """

    def __init__(self, config: Optional[LocalModelConfig] = None):
        self._config = config or LocalModelConfig()
        self._usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "call_count": 0,
        }

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
        通过 Ollama /api/chat 生成回复
        """
        start_time = time.time()
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        payload = {
            "model": self._config.model,
            "messages": ollama_messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "think": False,  # qwen3.5 non-thinking 模式
        }

        def _do_request():
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self._config.base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
                content = ""
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if obj.get("done"):
                        break
                    content += obj.get("message", {}).get("content", "")
                return {"message": {"content": content}}

        try:
            result = await asyncio.to_thread(_do_request)
            content = result.get("message", {}).get("content", "")

            # 估算 token（Ollama 不返回 usage，用字符数近似）
            prompt_tokens = sum(len(m.get("content", "")) for m in ollama_messages) // 4
            output_tokens = len(content) // 4

            self._usage["total_input_tokens"] += prompt_tokens
            self._usage["total_output_tokens"] += output_tokens
            self._usage["call_count"] += 1
            self._usage["total_cost"] = 0.0  # 本地模型无费用

            latency_ms = (time.time() - start_time) * 1000
            logger.debug(f"[LocalOllama] out={output_tokens} tokens | latency={latency_ms:.0f}ms | purpose={purpose}")

            return LLMResponse(
                content=content,
                model="local",
                tokens_used=output_tokens,
                latency_ms=latency_ms,
                success=True,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"[LocalOllama] 请求失败: {e}")
            return LLMResponse(
                content="",
                model="local",
                tokens_used=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e),
            )

    async def embed(self, text: str) -> list[float]:
        """通过 /api/embeddings 生成嵌入向量（使用 bge-m3）"""
        payload = {
            "model": self._config.embed_model,
            "prompt": text,
            "options": {"temperature": 0},
        }

        def _do():
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self._config.base_url}/api/embeddings",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp).get("embedding", [])

        try:
            embedding = await asyncio.to_thread(_do)
            # 归一化
            norm = sum(x**2 for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
            return embedding
        except Exception as e:
            logger.warning(f"[LocalOllama] 嵌入失败: {e}")
            return [0.0] * self._config.embed_dim

    def get_model_name(self) -> str:
        return self._config.model

    async def health_check(self) -> bool:
        """健康检查：检测 Ollama 服务是否可用"""
        try:
            req = urllib.request.Request(
                f"{self._config.base_url}/api/tags",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False