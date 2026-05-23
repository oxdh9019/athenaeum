"""
ollama_client.py — V0.3 Ollama 本地 LLM 客户端
使用 urllib 模式（参考 v0.2 embedding_ollama.py）
支持 qwen3.5:4b non-thinking 模式
"""

import asyncio
import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaLLMClient:
    """
    Ollama 本地模型客户端。

    支持:
    - qwen3.5:4b non-thinking 模式
    - 与 LLMClient 接口兼容（chat 方法签名一致）
    - 异步请求（通过 asyncio.to_thread）
    - Token 使用量追踪（无费用，仅统计）
    """

    def __init__(
        self,
        model: str = "qwen3.5:4b",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url
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
        max_tokens: int = 200,
    ) -> str:
        """
        通过 Ollama /api/chat 生成回复。
        对于 qwen3.5，发送 "think": false 禁用 thinking 模式。
        """
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        payload = {
            "model": self.model,
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
                f"{self.base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
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
        except Exception as e:
            logger.error(f"[Ollama] 请求失败: {e}")
            raise

        try:
            content = result.get("message", {}).get("content", "")
            # 估算 token（Ollama 不返回 usage，用字符数近似）
            prompt_tokens = sum(len(m.get("content", "")) for m in ollama_messages) // 4
            output_tokens = len(content) // 4

            self._usage["total_input_tokens"] += prompt_tokens
            self._usage["total_output_tokens"] += output_tokens
            self._usage["call_count"] += 1
            self._usage["total_cost"] = 0.0

            logger.debug(f"[Ollama] out={output_tokens} tokens | local (no cost)")
            return content

        except Exception as e:
            logger.error(f"[Ollama] 解析响应失败: {e}")
            raise

    async def embed(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        """通过 /api/embeddings 生成嵌入向量"""
        results = []

        for text in texts:
            def _do():
                payload = {
                    "model": self.model,
                    "prompt": text,
                    "options": {"temperature": 0},
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.base_url}/api/embeddings",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.load(resp).get("embedding", [])

            try:
                embedding = await asyncio.to_thread(_do)
                if normalize and embedding:
                    norm = sum(x**2 for x in embedding) ** 0.5
                    if norm > 0:
                        embedding = [x / norm for x in embedding]
                results.append(embedding)
            except Exception as e:
                logger.warning(f"[Ollama] 嵌入失败: {e}")
                results.append([0.0] * 1536)

        return results

    async def close(self) -> None:
        pass


class HybridLLMClient:
    """
    混合客户端：优先本地 Ollama，失败时回退到云端 LLM。
    """

    def __init__(self, ollama_model: str = "qwen3.5:4b", fallback_llm=None):
        self._ollama = OllamaLLMClient(model=ollama_model)
        self._fallback = fallback_llm
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
        max_tokens: int = 200,
    ) -> str:
        try:
            result = await self._ollama.chat(messages, system, temperature, max_tokens)
            self._usage["call_count"] += 1
            return result
        except Exception as e:
            if self._fallback:
                logger.warning(f"[Ollama] 失败，回退到云端: {e}")
                result = await self._fallback.chat(messages, system, temperature, max_tokens)
                u = self._fallback.usage
                self._usage["total_input_tokens"] += u.get("total_input_tokens", 0)
                self._usage["total_output_tokens"] += u.get("total_output_tokens", 0)
                self._usage["total_cost"] += u.get("total_cost", 0.0)
                self._usage["call_count"] += 1
                return result
            raise

    async def embed(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        return await self._ollama.embed(texts, normalize)

    async def close(self) -> None:
        if self._fallback:
            await self._fallback.close()
