# V0.5 Memory Arcade
# V0.7 Plugin Architecture
#
# 注意：V0.7 实际 LLM 实现走 `utils/llm_client.py`（LLMClient）+ `utils/ollama_client.py`（OllamaLLMClient），
# 不走 `core/clients/`。后者（实现 ILLMClient 接口的 LocalOllamaClient / MiniMaxClient）从未被实例化，
# 保留会误导新读者。两个并行路径已通过删除 core/clients/ 收拢为 utils 单一路径（audit 3.10 + 9.14 + 9.15）。
# 如果未来需要 ILLMClient 抽象，请基于 utils/* 适配，而不是恢复 core/clients/。

from .interfaces import ILLMClient, IModelRouter, LLMResponse, RouterStats, IntentType
from .plugin_registry import PluginRegistry, register_llm_client, register_router
from .model_router import ModelRouter, create_default_router