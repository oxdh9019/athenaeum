"""
world_will.py — V0.6 世界意志配置
控制叙事事件的生成风格和机会检测阈值
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WorldWill:
    """
    世界意志配置
    控制冲突频率、合作鼓励度、浪漫偏好、随机性
    用于调整叙事事件生成风格
    """
    conflict_frequency: float = 0.3  # 0.0-1.0，冲突事件发生概率
    cooperation_encouragement: float = 0.6  # 合作事件权重
    romance_bias: float = 0.3  # 浪漫事件权重
    randomness: float = 0.3  # 随机性程度

    @classmethod
    def from_yaml(cls, data: dict) -> "WorldWill":
        """
        从 YAML 配置创建 WorldWill 实例

        Args:
            data: world_will 段的配置字典

        Returns:
            WorldWill 实例
        """
        return cls(
            conflict_frequency=data.get("conflict_frequency", 0.3),
            cooperation_encouragement=data.get("cooperation_encouragement", 0.6),
            romance_bias=data.get("romance_bias", 0.3),
            randomness=data.get("randomness", 0.3),
        )

    @classmethod
    def from_world_config(cls, world_config: dict) -> "WorldWill":
        """
        从世界配置中提取 WorldWill

        Args:
            world_config: 世界配置字典

        Returns:
            WorldWill 实例
        """
        world_will_data = world_config.get("world_will", {})
        return cls.from_yaml(world_will_data)

    def should_trigger_conflict(self, base_probability: float = 0.1) -> bool:
        """
        根据 conflict_frequency 决定是否触发冲突事件

        Args:
            base_probability: 基础概率

        Returns:
            True 如果应该触发
        """
        threshold = base_probability * (1.0 + self.conflict_frequency)
        import random
        return random.random() < threshold

    def adjust_conflict_strength(self, base_strength: float) -> float:
        """
        根据 conflict_frequency 调整冲突强度

        Args:
            base_strength: 基础强度

        Returns:
            调整后的强度
        """
        # conflict_frequency 越高，冲突强度越高
        return base_strength * (0.5 + self.conflict_frequency)

    def should_encourage_cooperation(self) -> bool:
        """
        根据 cooperation_encouragement 决定是否鼓励合作

        Returns:
            True 如果应该鼓励
        """
        import random
        return random.random() < self.cooperation_encouragement

    def get_event_bias(self) -> str:
        """
        根据 romance_bias 和其他参数决定事件偏向

        Returns:
            事件类型偏向：conflict / cooperation / romance / neutral
        """
        import random
        r = random.random()

        if r < self.conflict_frequency:
            return "conflict"
        elif r < self.conflict_frequency + self.cooperation_encouragement * 0.5:
            return "cooperation"
        elif r < self.conflict_frequency + self.cooperation_encouragement * 0.5 + self.romance_bias:
            return "romance"
        else:
            return "neutral"

    def __repr__(self) -> str:
        return (f"WorldWill(conflict={self.conflict_frequency}, "
                f"cooperation={self.cooperation_encouragement}, "
                f"romance={self.romance_bias}, "
                f"randomness={self.randomness})")