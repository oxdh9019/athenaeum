"""
subconscious_engine.py — V0.7 潜意识规则匹配引擎
零 LLM 成本的 micro_action 生成
在心跳模式或对话间隙匹配环境触发词，产生下意识动作
"""

import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)


class SubconsciousRule:
    """潜意识规则数据结构"""

    def __init__(self, trigger: str, action: str, priority: float = 0.2):
        self.trigger = trigger      # 触发词，如"看到甜食"
        self.action = action        # 自动行为，如"目光多停留几秒，可能微笑"
        self.priority = priority    # 优先级 0.0-1.0

    def __repr__(self):
        return f"SubconsciousRule(trigger='{self.trigger}', action='{self.action}', priority={self.priority})"


class SoulConfig:
    """Soul 配置数据结构"""

    def __init__(
        self,
        core_desires: list = None,
        inner_conflict: Optional[dict] = None,
        subconscious_rules: list = None,
        behavioral_tendencies: dict = None,
        long_term_goals: list = None,
    ):
        self.core_desires = core_desires or []
        self.inner_conflict = inner_conflict  # {"pole_a": str, "pole_b": str, "description": str}
        self.subconscious_rules = subconscious_rules or []
        self.behavioral_tendencies = behavioral_tendencies or {}
        self.long_term_goals = long_term_goals or []

    @classmethod
    def from_dict(cls, data: dict) -> "SoulConfig":
        """从字典创建 SoulConfig"""
        return cls(
            core_desires=data.get("core_desires", []),
            inner_conflict=data.get("inner_conflict"),
            subconscious_rules=data.get("subconscious_rules", []),
            behavioral_tendencies=data.get("behavioral_tendencies", {}),
            long_term_goals=data.get("long_term_goals", []),
        )


class SubconsciousEngine:
    """
    潜意识规则匹配引擎

    功能:
    - 在心跳模式或对话间隙，匹配环境触发词
    - 产生零 LLM 成本的 micro_action
    - 集成到 HeartbeatMode 和 DialogueEngine
    """

    def __init__(self, agent_id: str, soul: SoulConfig = None):
        self._agent_id = agent_id
        self._soul = soul
        self._rules: list[SubconsciousRule] = []
        self._cooldown_ticks: dict[str, int] = {}  # 规则ID -> 剩余冷却Tick

        if soul and soul.subconscious_rules:
            for rule_data in soul.subconscious_rules:
                if isinstance(rule_data, dict):
                    self._rules.append(SubconsciousRule(
                        trigger=rule_data.get("trigger", ""),
                        action=rule_data.get("action", ""),
                        priority=rule_data.get("priority", 0.2),
                    ))
                elif isinstance(rule_data, str):
                    # 简单字符串格式: "trigger->action"
                    parts = rule_data.split("->")
                    if len(parts) == 2:
                        self._rules.append(SubconsciousRule(
                            trigger=parts[0].strip(),
                            action=parts[1].strip(),
                            priority=0.2,
                        ))

    def set_soul(self, soul: SoulConfig):
        """设置/更新 Soul 配置"""
        self._soul = soul
        self._rules = []
        if soul and soul.subconscious_rules:
            for rule_data in soul.subconscious_rules:
                if isinstance(rule_data, dict):
                    self._rules.append(SubconsciousRule(
                        trigger=rule_data.get("trigger", ""),
                        action=rule_data.get("action", ""),
                        priority=rule_data.get("priority", 0.2),
                    ))

    def match(self, agent, world_snapshot: dict) -> Optional[dict]:
        """
        匹配潜意识规则

        Args:
            agent: Agent 对象（用于获取名字等信息）
            world_snapshot: 世界状态快照，包含位置、可见物体、附近角色等

        Returns:
            匹配的 micro_action dict 或 None
            {
                "micro_action": str,      # 动作描述
                "priority": float,         # 优先级
                "rule_trigger": str,       # 触发的规则
            }
        """
        if not self._rules:
            return None

        # 清理冷却
        self._clean_cooldowns()

        # 获取环境信息
        location = world_snapshot.get("location", "")
        visible_objects = world_snapshot.get("visible_objects", [])
        nearby_agents = world_snapshot.get("nearby_agents", [])
        time_of_day = world_snapshot.get("time_of_day", "")

        # 构建检测文本
        detection_text = f"{location} {' '.join(visible_objects)} {' '.join(nearby_agents)} {time_of_day}".lower()

        # 匹配规则
        for rule in self._rules:
            trigger = rule.trigger.lower()

            # 检查冷却
            if trigger in self._cooldown_ticks:
                continue

            # 关键词匹配
            if self._trigger_match(trigger, detection_text):
                # 随机性：按优先级概率通过
                if random.random() > rule.priority:
                    continue

                # 设置冷却（3-8 Tick）
                self._cooldown_ticks[trigger] = random.randint(3, 8)

                logger.debug(
                    f"[SubconsciousEngine] [{self._agent_id}] 触发: '{rule.trigger}' → '{rule.action}'"
                )

                return {
                    "micro_action": rule.action,
                    "priority": rule.priority,
                    "rule_trigger": rule.trigger,
                }

        return None

    def _trigger_match(self, trigger: str, detection_text: str) -> bool:
        """
        检查触发词是否匹配

        Args:
            trigger: 触发词（如"甜食"、"书"）
            detection_text: 检测文本（已转小写）

        Returns:
            True = 匹配
        """
        trigger_words = trigger.replace(",", " ").split()

        # 所有触发词都必须在检测文本中
        for word in trigger_words:
            if word.strip() and word.strip() not in detection_text:
                return False
        return True

    def _clean_cooldowns(self):
        """清理过期的冷却"""
        expired = [k for k, v in self._cooldown_ticks.items() if v <= 0]
        for k in expired:
            del self._cooldown_ticks[k]

        # 减冷却
        for k in self._cooldown_ticks:
            self._cooldown_ticks[k] -= 1

    def tick_update(self):
        """每 Tick 更新（清理冷却）"""
        self._clean_cooldowns()

    def get_micro_action_for_dialogue(
        self,
        agent,
        world_snapshot: dict,
        emotion_arousal: float = 0.5,
    ) -> Optional[str]:
        """
        在对话中生成微观动作

        Args:
            agent: Agent 对象
            world_snapshot: 世界状态快照
            emotion_arousal: 情绪唤醒度（0.0-1.0），越高越可能产生动作

        Returns:
            micro_action 字符串或 None
        """
        if not self._rules:
            return None

        # 基础概率 15%，高唤醒度时最高 35%
        base_prob = 0.15
        arousal_bonus = (emotion_arousal - 0.5) * 0.4 if emotion_arousal > 0.5 else 0
        probability = base_prob + arousal_bonus

        if random.random() > probability:
            return None

        result = self.match(agent, world_snapshot)
        if result:
            return result["micro_action"]

        return None

    def get_status(self) -> dict:
        """获取状态（用于调试）"""
        return {
            "agent_id": self._agent_id,
            "rule_count": len(self._rules),
            "active_rules": [
                {"trigger": r.trigger, "action": r.action, "priority": r.priority}
                for r in self._rules
            ],
            "cooldowns": self._cooldown_ticks.copy(),
        }