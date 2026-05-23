# V0.5 Memory Arcade
# V0.7 Plugin Architecture

from .interfaces import ILLMClient, IModelRouter, LLMResponse, RouterStats, IntentType
from .plugin_registry import PluginRegistry, register_llm_client, register_router
from .clients import LocalOllamaClient, MiniMaxClient, LocalModelConfig
from .model_router import ModelRouter, create_default_router