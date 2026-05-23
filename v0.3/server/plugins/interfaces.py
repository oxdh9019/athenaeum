"""
interfaces.py — V0.3 插件化架构接口定义
遵循 SPEC 5.4-5.7 规范
"""

from abc import ABC, abstractmethod
from typing import Optional, Any
from enum import Enum
import asyncio


class TickType(Enum):
    """Tick 分级类型"""
    SILENT = "silent"   # 静默Tick，不调用LLM
    NORMAL = "normal"   # 普通Tick，标准LLM调用
    CRITICAL = "critical"  # 关键Tick，高频LLM调用


class IDesireEngine(ABC):
    """欲望引擎接口 - 负责管理角色需求状态"""

    @abstractmethod
    def get_active_needs(self, agent_id: str) -> list[Any]:
        """获取当前活跃需求列表"""
        pass

    @abstractmethod
    def get_top_need(self, agent_id: str) -> Optional[Any]:
        """获取最强烈的需求"""
        pass

    @abstractmethod
    def update_from_environment(self, agent_id: str, event_text: str) -> None:
        """根据环境事件更新需求"""
        pass

    @abstractmethod
    def update_from_interaction(self, agent_id: str, intent_type: str, emotion: str, positive: bool) -> None:
        """根据互动结果更新需求"""
        pass

    @abstractmethod
    def as_prompt_fragment(self, agent_id: str) -> str:
        """生成需求描述片段"""
        pass


class IMemorySystem(ABC):
    """记忆系统接口 - 短期+长期记忆管理"""

    @abstractmethod
    def add_short_term(self, agent_id: str, role: str, content: str) -> None:
        """添加短期记忆"""
        pass

    @abstractmethod
    def get_context(self, agent_id: str, limit: int = 20) -> list[dict]:
        """获取记忆上下文"""
        pass

    @abstractmethod
    async def summarize_and_store_long_term(self, agent_id: str, llm: Any) -> None:
        """将短期记忆摘要存入长期记忆"""
        pass

    @abstractmethod
    async def retrieve_relevant(self, agent_id: str, query: str, limit: int = 5) -> list[dict]:
        """基于嵌入相似度检索相关长期记忆"""
        pass

    @abstractmethod
    def decay_long_term(self, decay_factor: float = 0.95) -> None:
        """长期记忆衰减"""
        pass


class ILLMClient(ABC):
    """LLM客户端接口 - 统一LLM调用"""

    @abstractmethod
    async def chat(self, messages: list[dict], system: Optional[str] = None,
                   temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """发送对话请求"""
        pass

    @abstractmethod
    async def embed(self, texts: list[str], normalize: bool = True) -> list[list[float]]:
        """获取文本嵌入向量"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass


class IEventBus(ABC):
    """事件总线接口 - 系统内事件发布订阅"""

    @abstractmethod
    async def publish(self, event_type: str, data: dict) -> None:
        """发布事件"""
        pass

    @abstractmethod
    async def subscribe(self, event_type: str, callback) -> None:
        """订阅事件"""
        pass

    @abstractmethod
    async def unsubscribe(self, event_type: str, callback) -> None:
        """取消订阅"""
        pass


class ISpaceSystem(ABC):
    """空间系统接口 - 位置和移动管理"""

    @abstractmethod
    def get_location(self, agent_id: str) -> Optional[str]:
        """获取角色当前位置"""
        pass

    @abstractmethod
    def move_agent(self, agent_id: str, target_location: str) -> bool:
        """移动角色到目标位置"""
        pass

    @abstractmethod
    def get_neighbors(self, agent_id: str) -> list[str]:
        """获取附近其他角色ID列表"""
        pass

    @abstractmethod
    def get_location_capacity(self, location: str) -> int:
        """获取位置容量"""
        pass

    @abstractmethod
    def register_location(self, location_id: str, name: str, tags: list[str], capacity: int) -> None:
        """注册位置"""
        pass


class INarrativeEngine(ABC):
    """叙事引擎接口 - 生成世界事件和叙事注入"""

    @abstractmethod
    async def generate_event(self, world_state: dict) -> Optional[dict]:
        """生成叙事事件"""
        pass

    @abstractmethod
    def get_story_timeline(self) -> list[dict]:
        """获取故事时间线"""
        pass

    @abstractmethod
    def calculate_stage_momentum(self, location: str, agent_count: int, relationship_complexity: float) -> float:
        """计算舞台动量 - 影响叙事注入概率"""
        pass


class IDialogueManager(ABC):
    """对话管理器接口 - 多角色对话协调"""

    @abstractmethod
    async def trigger_dialogue(self, agent_a_id: str, agent_b_id: str) -> None:
        """触发两个角色对话"""
        pass

    @abstractmethod
    def is_agent_active(self, agent_id: str) -> bool:
        """检查角色是否正在对话中"""
        pass

    @abstractmethod
    async def interrupt_dialogue(self, agent_id: str) -> None:
        """中断角色的当前对话"""
        pass


class IScheduler(ABC):
    """调度器接口 - 分级Tick调度"""

    @abstractmethod
    def evaluate_tick_type(self, world_state: dict) -> TickType:
        """评估当前Tick类型"""
        pass

    @abstractmethod
    def should_process_agent(self, agent_id: str, tick_type: TickType) -> bool:
        """判断是否应该处理该角色"""
        pass
