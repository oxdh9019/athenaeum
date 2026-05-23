"""
interfaces.py — V0.7 插件化架构核心接口定义
定义 ILLMClient、IModelRouter 等抽象接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


class IntentType(Enum):
    """意图类型枚举（用于路由决策）"""
    GREET = "greet"
    ASK = "ask"
    WAIT = "wait"
    MOVE = "move"
    SHARE = "share"
    INVITE = "invite"
    FLEE = "flee"
    CONFESS = "confess"
    SUMMARIZE = "summarize"
    NARRATE = "narrate"
    WORLD_GENERATE = "world_generate"
    UNKNOWN = "unknown"


@dataclass
class LLMResponse:
    """LLM 调用响应"""
    content: str
    model: str  # "local" 或 "cloud"
    tokens_used: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass
class RouterStats:
    """路由统计信息（供仪表盘查询）"""
    local_calls: int = 0
    cloud_calls: int = 0
    degrade_active: bool = False
    budget_remaining: float = 1.0  # 剩余预算比例
    budget_ratio: float = 0.0  # 已使用比例
    daily_budget: float = 10.0  # 美元
    last_reset: Optional[datetime] = None
    total_cost: float = 0.0


class ILLMClient(ABC):
    """
    统一 LLM 调用接口
    所有 LLM 客户端（本地/云端）必须实现此接口
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        purpose: str = "general"
    ) -> LLMResponse:
        """
        统一对话接口

        Args:
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            system: 系统提示词
            temperature: 温度参数
            max_tokens: 最大 token 数
            purpose: 调用目的（用于路由决策和日志）

        Returns:
            LLMResponse: 包含生成内容和元数据
        """
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        生成嵌入向量（用于记忆检索）

        Args:
            text: 输入文本

        Returns:
            list[float]: 嵌入向量
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """返回模型名称"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass


class IModelRouter(ABC):
    """
    模型路由接口
    根据意图类型、附身状态和预算决定使用哪个模型
    """

    @abstractmethod
    def route(
        self,
        intent_type: str,
        is_possessed: bool = False,
        budget_ratio: float = 0.0
    ) -> str:
        """
        决定使用哪个模型

        Args:
            intent_type: 意图类型字符串
            is_possessed: 是否用户附身
            budget_ratio: 当前预算使用比例 (0.0-1.0)

        Returns:
            str: "local" 或 "cloud"
        """
        pass

    @abstractmethod
    def get_stats(self) -> RouterStats:
        """返回路由统计，供仪表盘查询"""
        pass

    @abstractmethod
    def record_call(self, model: str, tokens: int, cost: float):
        """记录一次调用（用于成本统计）"""
        pass

    @abstractmethod
    def reset_daily_budget(self):
        """重置每日预算（每日 00:00 调用）"""
        pass


class IDesireEngine(ABC):
    """
    欲望引擎接口
    定义 Agent 欲望驱动行为的抽象
    """
    pass


class IMemorySystem(ABC):
    """
    记忆系统接口
    定义长期记忆存储和检索的抽象
    """
    pass


class IEventBus(ABC):
    """
    事件总线接口
    定义系统内事件发布订阅的抽象
    """
    pass