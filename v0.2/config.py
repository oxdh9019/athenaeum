"""
config.py — V0.2 配置类，便于切换 LLM 模型
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """LLM 调用配置"""
    model: str = "MiniMax-M2.7"
    intent_temperature: float = 0.2    # 意图生成 — 低温度，保持稳定
    dialogue_temperature: float = 0.8  # 对话生成 — 高温度，有创造性
    max_tokens: int = 2000
    api_key_env: str = "ANTHROPIC_API_KEY"
    base_url_env: str = "ANTHROPIC_BASE_URL"
    default_base_url: str = "https://api.minimaxi.com/anthropic"

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ValueError(f"环境变量 {self.api_key_env} 未设置")
        return key

    @property
    def base_url(self) -> str:
        return os.environ.get(self.base_url_env, self.default_base_url)


@dataclass
class DialogueConfig:
    """对话引擎配置"""
    max_turns: int = 20              # 最大对话轮次（单方）
    loop_similarity_threshold: float = 0.7
    loop_window: int = 3             # 检测最近 N 轮
    memory_max: int = 20
    st_cache_dir: str = "/Volumes/Ollama-Models/.cache/huggingface/hub"  # sentence-transformers 缓存路径
