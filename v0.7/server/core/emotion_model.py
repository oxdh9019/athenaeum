"""
emotion_model.py — V0.7 情绪模型
效价(Valence) + 唤醒度(Arousal) 二维情绪系统
规则驱动，不消耗 LLM
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmotionState:
    """情绪状态"""
    valence: float       # -1.0 ~ 1.0 (消极 ~ 积极)
    arousal: float      # 0.0 ~ 1.0 (平静 ~ 激动)
    label: str          # 情绪标签

    @staticmethod
    def from_valence_arousal(valence: float, arousal: float) -> 'EmotionState':
        """根据效价和唤醒度确定情绪标签"""
        # 效价高+唤醒高 = 兴奋/开心
        # 效价高+唤醒低 = 满足/放松
        # 效价低+唤醒高 = 愤怒/焦虑
        # 效价低+唤醒低 = 悲伤/沮丧

        if valence >= 0.3 and arousal >= 0.5:
            label = "happy"
        elif valence >= 0.3 and arousal < 0.5:
            label = "content"
        elif valence <= -0.3 and arousal >= 0.5:
            label = "anxious"
        elif valence <= -0.3 and arousal < 0.5:
            label = "sad"
        elif arousal >= 0.7:
            label = "curious"
        else:
            label = "neutral"

        return EmotionState(valence=valence, arousal=arousal, label=label)


class EmotionModel:
    """
    情绪模型
    基于效价和唤醒度计算情绪状态
    """

    def __init__(self, agent_id: str, initial_valence: float = 0.0, initial_arousal: float = 0.3):
        self._agent_id = agent_id
        self._valence = initial_valence
        self._arousal = initial_arousal
        self._label = "neutral"
        self._history: list[EmotionState] = []

        # 记录最近的社会反馈（用于情绪计算）
        self._recent_social_feedback: list[float] = []  # 关系变化值

    @property
    def state(self) -> EmotionState:
        return EmotionState.from_valence_arousal(self._valence, self._arousal)

    @property
    def valence(self) -> float:
        return self._valence

    @property
    def arousal(self) -> float:
        return self._arousal

    @property
    def label(self) -> str:
        return self._label

    def get_state(self) -> dict:
        """获取情绪状态（用于 Prompt）"""
        return {
            "valence": self._valence,
            "arousal": self._arousal,
            "label": self._label,
        }

    def update(
        self,
        desire_fulfillment: float = 0.5,
        goal_progress: float = 0.0,
        social_feedback: float = 0.0
    ):
        """
        更新情绪状态

        Args:
            desire_fulfillment: 欲望满足度 (0.0 ~ 1.0)，越高情绪越正向
            goal_progress: 目标进度增量 (负值表示退步)
            social_feedback: 最近社交反馈 (-1.0 ~ 1.0)，正值正向，负值负向
        """
        # 保留历史
        self._history.append(self.state)

        # 1. 欲望满足影响效价
        # 欲望满足度高 → 效价正向，欲望满足度低 → 效价负向
        desire_delta = (desire_fulfillment - 0.5) * 0.15  # 最多 ±0.075
        self._valence += desire_delta

        # 2. 目标进度影响效价和唤醒度
        if goal_progress > 0:
            self._valence += goal_progress * 0.1  # 正向进度提升情绪
            self._arousal += goal_progress * 0.05   # 成就感带来轻微激动
        elif goal_progress < 0:
            self._valence += goal_progress * 0.15   # 退步更影响情绪
            self._arousal += abs(goal_progress) * 0.1  # 挫败感增加唤醒

        # 3. 社交反馈
        if social_feedback != 0:
            self._valence += social_feedback * 0.2
            # 高外向性对社交反馈更敏感
            self._valence += social_feedback * 0.1  # 基本影响
            self._arousal += abs(social_feedback) * 0.1  # 社交带来唤醒

        # 4. 自然衰减：唤醒度逐渐降低（接近平静）
        self._arousal *= 0.95

        # 5. 限制范围
        self._valence = max(-1.0, min(1.0, self._valence))
        self._arousal = max(0.0, min(1.0, self._arousal))

        # 6. 更新标签
        self._label = self.state.label

        # 记录社交反馈用于后续计算
        if social_feedback != 0:
            self._recent_social_feedback.append(social_feedback)
            # 只保留最近5次
            if len(self._recent_social_feedback) > 5:
                self._recent_social_feedback.pop(0)

        logger.debug(
            f"[EmotionModel] [{self._agent_id}] valence={self._valence:.2f}, "
            f"arousal={self._arousal:.2f}, label={self._label}"
        )

    def add_social_feedback(self, feedback: float):
        """
        添加社交反馈（每次社交后调用）

        Args:
            feedback: 关系变化值 (-1.0 ~ 1.0)
        """
        self._recent_social_feedback.append(feedback)
        if len(self._recent_social_feedback) > 5:
            self._recent_social_feedback.pop(0)

    def get_average_social_feedback(self) -> float:
        """获取平均社交反馈"""
        if not self._recent_social_feedback:
            return 0.0
        return sum(self._recent_social_feedback) / len(self._recent_social_feedback)

    def adjust_valence(self, delta: float):
        """直接调整效价（用于目标完成等事件）"""
        self._valence = max(-1.0, min(1.0, self._valence + delta))
        self._label = self.state.label

    def adjust_arousal(self, delta: float):
        """直接调整唤醒度"""
        self._arousal = max(0.0, min(1.0, self._arousal + delta))
        self._label = self.state.label

    def apply_event(self, event_type: str, event_data: dict = None):
        """
        应用外部事件影响情绪

        Args:
            event_type: 事件类型（narrative / danger / social）
            event_data: 事件数据
        """
        if event_type == "danger":
            # 危险事件：唤醒度大幅上升，效价下降
            self._arousal = min(1.0, self._arousal + 0.4)
            self._valence = max(-1.0, self._valence - 0.2)
            self._label = self.state.label

        elif event_type == "narrative":
            # 叙事事件：中等唤醒，效价根据事件性质调整
            self._arousal = min(1.0, self._arousal + 0.2)
            sentiment = event_data.get("sentiment", 0) if event_data else 0
            self._valence = max(-1.0, min(1.0, self._valence + sentiment * 0.15))
            self._label = self.state.label

        elif event_type == "positive_social":
            # 正向社交：效价上升
            self._valence = min(1.0, self._valence + 0.15)
            self._arousal = min(1.0, self._arousal + 0.1)
            self._label = self.state.label

        elif event_type == "negative_social":
            # 负向社交：效价下降
            self._valence = max(-1.0, self._valence - 0.15)
            self._label = self.state.label

        logger.info(
            f"[EmotionModel] [{self._agent_id}] 事件影响: {event_type} "
            f"→ valence={self._valence:.2f}, arousal={self._arousal:.2f}"
        )