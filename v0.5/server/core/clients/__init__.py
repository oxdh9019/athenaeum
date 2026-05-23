"""
clients/__init__.py — V0.7 LLM 客户端实现
"""

from .local_ollama_client import LocalOllamaClient, LocalModelConfig
from .minimax_client import MiniMaxClient

__all__ = ["LocalOllamaClient", "LocalModelConfig", "MiniMaxClient"]