"""
collective_mood.py — V0.6 集体情绪评估
计算所有在线角色的平均情绪状态和趋势
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MoodState:
    """情绪状态快照"""
    tick: int
    avg_tr: float  # Trust 平均值
    avg_cs: float  # Cooperation/Safety 平均值
    avg_sa: float  # Self-actualization 平均值
    trend: str  # rising_tension / stable / relaxing
    mood_label: str  # 氛围描述


class CollectiveMood:
    """
    集体情绪评估器
    - 每个 Tick 收集所有在线角色的 TR, CS, SA 值，计算平均值
    - 计算趋势（最近 5 Tick 的变化率）
    - 标记氛围（rising_tension / stable / relaxing）
    - 所有计算由本地规则完成，不调用 LLM
    """

    def __init__(self, world):
        self._world = world
        self._history: list[MoodState] = []
        self._max_history = 10  # 保留最近 10 个状态

    def evaluate(self, agents: list) -> MoodState:
        """
        评估当前集体情绪

        Args:
            agents: 在线角色列表

        Returns:
            MoodState 当前情绪状态
        """
        if not agents:
            return MoodState(
                tick=getattr(self._world, '_tick_id', 0),
                avg_tr=0.5, avg_cs=0.5, avg_sa=0.5,
                trend="stable",
                mood_label="无角色在线"
            )

        # 收集 TR, CS, SA 值
        tr_values = []
        cs_values = []
        sa_values = []

        for agent in agents:
            # 获取角色的 TR, CS, SA 值
            if hasattr(agent, 'get_tr'):
                tr_values.append(agent.get_tr())
            if hasattr(agent, 'get_cs'):
                cs_values.append(agent.get_cs())
            if hasattr(agent, 'get_sa'):
                sa_values.append(agent.get_sa())

        # 计算平均值
        avg_tr = sum(tr_values) / len(tr_values) if tr_values else 0.5
        avg_cs = sum(cs_values) / len(cs_values) if cs_values else 0.5
        avg_sa = sum(sa_values) / len(sa_values) if sa_values else 0.5

        # 计算趋势
        trend = self._calculate_trend()

        # 标记氛围
        mood_label = self._get_mood_label(avg_tr, avg_cs, avg_sa)

        tick = getattr(self._world, '_tick_id', 0)
        state = MoodState(
            tick=tick,
            avg_tr=avg_tr,
            avg_cs=avg_cs,
            avg_sa=avg_sa,
            trend=trend,
            mood_label=mood_label,
        )

        # 记录历史
        self._history.append(state)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        logger.info(f"[CollectiveMood] tick={tick}, TR={avg_tr:.2f}, CS={avg_cs:.2f}, SA={avg_sa:.2f}, trend={trend}, mood={mood_label}")
        return state

    def _calculate_trend(self) -> str:
        """计算最近5 Tick的趋势"""
        if len(self._history) < 2:
            return "stable"

        # 取最近 5 个状态
        recent = self._history[-5:] if len(self._history) >= 5 else self._history

        # 计算 TR 的变化率
        tr_values = [s.avg_tr for s in recent]
        tr_change = tr_values[-1] - tr_values[0]

        if tr_change > 0.1:
            return "rising_tension"
        elif tr_change < -0.1:
            return "relaxing"
        else:
            return "stable"

    def _get_mood_label(self, avg_tr: float, avg_cs: float, avg_sa: float) -> str:
        """根据平均值确定氛围标签"""
        # 综合判断
        if avg_tr > 0.7 and avg_cs < 0.4:
            return "紧张对立"
        elif avg_tr > 0.6 and avg_cs > 0.6:
            return "和谐合作"
        elif avg_sa > 0.7:
            return "活力充沛"
        elif avg_tr < 0.4 and avg_cs < 0.4:
            return "低迷冷漠"
        elif avg_tr < 0.3:
            return "冲突频发"
        else:
            return "平稳运行"

    def get_mood(self) -> str:
        """返回当前氛围标签"""
        if not self._history:
            return "stable"
        return self._history[-1].mood_label

    def get_trend(self) -> str:
        """返回最近趋势，供 opportunity_detector 使用"""
        if not self._history:
            return "stable"
        return self._history[-1].trend

    def get_latest_state(self) -> Optional[MoodState]:
        """返回最新的情绪状态"""
        return self._history[-1] if self._history else None