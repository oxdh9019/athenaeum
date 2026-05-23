"""
forgetting_curve.py — V0.5 遗忘曲线实现
根据 Ebbinghaus 遗忘曲线模型计算记忆衰减
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """记忆条目"""
    memory_id: str
    agent_id: str
    content: str  # 记忆摘要文本
    tick_created: int  # 创建时的 tick
    importance: float  # 重要性 0.0-1.0
    emotion: str  # 情感基调
    is_core: bool = False  # 是否为核心记忆（不可删除）
    context: str = ""  # 上下文信息（涉及角色、场景等）

    def calculate_score(self, current_tick: int, neuroticism: float = 0.5) -> float:
        """
        计算记忆评分：score = relevance * importance * exp(-λ * Δt)

        λ 根据角色 neuroticism 动态调整：
        - 高神经质 (neuroticism > 0.6): λ 值较低，遗忘更慢
        - 低神经质 (neuroticism < 0.4): λ 值较高，遗忘更快
        """
        if self.is_core:
            return 1.0  # 核心记忆永远不衰减

        delta_t = current_tick - self.tick_created

        # λ 计算：neuroticism 越高，λ 越低（遗忘更慢）
        # λ 范围: 0.01 (极高神经质) ~ 0.05 (极低神经质)
        lambda_base = 0.03
        lambda_adjustment = (0.5 - neuroticism) * 0.04
        lambda_value = lambda_base + lambda_adjustment

        decay = math.exp(-lambda_value * delta_t)
        score = self.importance * decay

        return score

    def should_delete(self, current_tick: int, neuroticism: float = 0.5) -> bool:
        """判断记忆是否应该被删除"""
        if self.is_core:
            return False

        score = self.calculate_score(current_tick, neuroticism)
        # 删除条件：score < 0.1 且 importance < 0.2
        return score < 0.1 and self.importance < 0.2


class ForgettingCurve:
    """
    遗忘曲线管理器
    管理单个 Agent 的记忆衰减和删除
    """

    def __init__(self, agent_id: str, neuroticism: float = 0.5):
        self._agent_id = agent_id
        self._neuroticism = neuroticism
        self._memories: dict[str, MemoryEntry] = {}

    def add_memory(self, memory: MemoryEntry) -> None:
        """添加记忆条目"""
        self._memories[memory.memory_id] = memory
        logger.info(f"[ForgettingCurve] [{self._agent_id}] 添加记忆 {memory.memory_id}, importance={memory.importance:.2f}")

    def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取单条记忆"""
        return self._memories.get(memory_id)

    def get_all_memories(self) -> list[MemoryEntry]:
        """获取所有记忆（用于检索）"""
        return list(self._memories.values())

    def mark_as_core(self, memory_id: str) -> None:
        """将记忆标记为核心记忆（关系变化 > 0.2 时调用）"""
        if memory_id in self._memories:
            self._memories[memory_id].is_core = True
            self._memories[memory_id].importance = 1.0
            logger.info(f"[ForgettingCurve] [{self._agent_id}] 记忆 {memory_id} 标记为核心记忆")

    def update_importance(self, memory_id: str, new_importance: float) -> None:
        """更新记忆重要性"""
        if memory_id in self._memories:
            self._memories[memory_id].importance = new_importance

    def prune_memories(self, current_tick: int) -> list[str]:
        """
        清理过期记忆，返回被删除的记忆 ID 列表
        """
        to_delete = []
        for memory_id, memory in self._memories.items():
            if memory.should_delete(current_tick, self._neuroticism):
                to_delete.append(memory_id)

        for memory_id in to_delete:
            del self._memories[memory_id]
            logger.info(f"[ForgettingCurve] [{self._agent_id}] 删除记忆 {memory_id}")

        return to_delete

    def get_recent_memories(self, current_tick: int, max_count: int = 10) -> list[MemoryEntry]:
        """
        获取最近的重要记忆（按创建时间倒序）
        """
        sorted_memories = sorted(
            self._memories.values(),
            key=lambda m: m.tick_created,
            reverse=True
        )
        return sorted_memories[:max_count]

    def size(self) -> int:
        """返回当前记忆数量"""
        return len(self._memories)