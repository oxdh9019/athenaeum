"""
opportunity_detector.py — V0.6 机会检测规则引擎
扫描角色位置和关系，生成冲突/浪漫/合作机会信号
"""

import logging
from dataclasses import dataclass
from typing import Optional
from itertools import combinations

logger = logging.getLogger(__name__)


@dataclass
class OpportunitySignal:
    """机会信号"""
    signal_type: str  # conflict / romance / cooperation
    participants: tuple[str, str]  # (agent_a_id, agent_b_id)
    confidence: float = 0.5  # 置信度 0.0-1.0


class OpportunityDetector:
    """
    本地规则引擎机会扫描器
    - 每个 Tick 扫描所有位置
    - 检测冲突机会（关系值 < 0.3）
    - 检测浪漫机会（关系值 > 0.7 + 勇气/忠诚满足阈值）
    - 检测合作机会（性格互补 + 世界氛围紧张）
    - 信号仅包含类型和涉及角色 ID，不包含事件内容
    """

    def __init__(self, world, collective_mood):
        """
        Args:
            world: WorldEngine 实例
            collective_mood: CollectiveMood 实例
        """
        self._world = world
        self._mood = collective_mood

    def scan(self) -> list[OpportunitySignal]:
        """
        扫描所有位置，生成机会信号列表

        Returns:
            OpportunitySignal 列表
        """
        signals = []

        # 使用 WorldEngine 的公开 API 获取所有位置和角色
        try:
            locations = self._world.get_all_locations()
        except AttributeError:
            logger.warning("[OpportunityDetector] WorldEngine 没有 get_all_locations 方法")
            return signals

        for loc in locations:
            loc_name = loc if isinstance(loc, str) else getattr(loc, 'name', str(loc))
            try:
                agents = self._world.get_agents_at_location(loc_name)
            except AttributeError:
                continue

            if len(agents) < 2:
                continue

            # 检查所有角色对
            for a_id, b_id in combinations(agents, 2):
                signal = self._check_pair(a_id, b_id)
                if signal:
                    signals.append(signal)

        logger.info(f"[OpportunityDetector] 扫描完成，检测到 {len(signals)} 个机会信号")
        return signals

    def _check_pair(self, a_id: str, b_id: str) -> Optional[OpportunitySignal]:
        """检查一对角色是否产生机会"""
        # 获取关系
        rel = self._world.get_relationship(a_id, b_id)
        if not rel:
            return None

        strength = rel if isinstance(rel, float) else getattr(rel, 'strength', 0.5)

        # 冲突机会：关系值 < 0.3
        if strength < 0.3:
            return OpportunitySignal(
                signal_type="conflict",
                participants=(a_id, b_id),
                confidence=1.0 - strength  # 关系越低，冲突置信度越高
            )

        # 浪漫机会：关系值 > 0.7 + 勇气/忠诚满足阈值
        elif strength > 0.7:
            agent_a = self._world.get_agent(a_id)
            agent_b = self._world.get_agent(b_id)
            if agent_a and agent_b and self._check_romance_traits(agent_a, agent_b):
                return OpportunitySignal(
                    signal_type="romance",
                    participants=(a_id, b_id),
                    confidence=strength  # 关系越高，浪漫置信度越高
                )

        # 合作机会：性格互补（高同理心+高野心）+ 世界氛围紧张
        else:
            agent_a = self._world.get_agent(a_id)
            agent_b = self._world.get_agent(b_id)
            if agent_a and agent_b:
                if self._check_cooperation_traits(agent_a, agent_b):
                    if self._mood.get_trend() == "rising_tension":
                        return OpportunitySignal(
                            signal_type="cooperation",
                            participants=(a_id, b_id),
                            confidence=0.7
                        )

        return None

    def _check_romance_traits(self, a, b) -> bool:
        """检查浪漫机会：勇气 + 忠诚满足阈值"""
        try:
            a_courage = getattr(a, 'courage', 0.5)
            a_loyalty = getattr(a, 'loyalty', 0.5)
            b_courage = getattr(b, 'courage', 0.5)
            b_loyalty = getattr(b, 'loyalty', 0.5)

            return (a_courage + a_loyalty > 1.2) or (b_courage + b_loyalty > 1.2)
        except Exception as e:
            logger.warning(f"[OpportunityDetector] 浪漫特质检查失败: {e}")
            return False

    def _check_cooperation_traits(self, a, b) -> bool:
        """检查合作机会：高同理心 + 高野心的互补组合"""
        try:
            a_empathy = getattr(a, 'empathy', 0.5)
            a_ambition = getattr(a, 'ambition', 0.5)
            b_empathy = getattr(b, 'empathy', 0.5)
            b_ambition = getattr(b, 'ambition', 0.5)

            return (a_empathy > 0.7 and b_ambition > 0.7) or \
                   (b_empathy > 0.7 and a_ambition > 0.7)
        except Exception as e:
            logger.warning(f"[OpportunityDetector] 合作特质检查失败: {e}")
            return False