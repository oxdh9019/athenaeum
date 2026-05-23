"""
personality_filter.py — V0.7 性格过滤规则
对 LLM 生成的候选意图进行性格过滤
纯规则引擎，不调用 LLM
"""

import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PersonalityFilter:
    """
    性格过滤器
    根据 Big Five 性格参数对候选意图进行过滤或调整
    """

    def __init__(self, personality: dict = None, tendencies: dict = None):
        self._personality = personality or {}
        self._tendencies = tendencies or {}

    def set_personality(self, personality: dict):
        self._personality = personality

    def set_tendencies(self, tendencies: dict):
        self._tendencies = tendencies

    def filter(self, intent: dict) -> Optional[dict]:
        """
        对意图进行性格过滤

        Args:
            intent: 意图字典，包含 action_type, urgency, reasoning 等

        Returns:
            过滤后的意图（返回 None 表示否决）
        """
        if not intent:
            return None

        action_type = intent.get("action_type", "")
        neuroticism = self._personality.get("neuroticism", 0.5)
        extraversion = self._personality.get("extraversion", 0.5)
        openness = self._personality.get("openness", 0.5)
        conscientiousness = self._personality.get("conscientiousness", 0.5)
        agreeableness = self._personality.get("agreeableness", 0.5)

        # === 规则1：高神经质 - 过滤高风险意图 ===
        if neuroticism > 0.7:
            if action_type in ("confront", "explore_dangerous", "take_risk"):
                if random.random() < 0.7:  # 70% 概率否决
                    logger.info(f"[PersonalityFilter] 否决高风险意图 (高神经质): {action_type}")
                    return None

        # === 规则2：低外向性 - 降低社交类意图优先级 ===
        if extraversion < 0.3:
            if action_type in ("social", "greet_stranger", "initiate_conversation"):
                intent["urgency"] = intent.get("urgency", 0.5) * 0.5  # 削弱50%
                logger.info(f"[PersonalityFilter] 削弱社交意图 (低外向): urgency -> {intent['urgency']:.2f}")

        # === 规则3：低开放性 - 过滤探索类意图 ===
        if openness < 0.3:
            if action_type == "exploration":
                if random.random() < 0.6:  # 60% 概率否决
                    logger.info(f"[PersonalityFilter] 否决探索意图 (低开放性)")
                    return None

        # === 规则4：高尽责性 - 增加目标驱动意图优先级 ===
        if conscientiousness > 0.7:
            if intent.get("mode") == "goal_driven" or intent.get("goal_related"):
                intent["urgency"] = min(1.0, intent.get("urgency", 0.5) * 1.3)
                logger.info(f"[PersonalityFilter] 增强目标意图 (高尽责): urgency -> {intent['urgency']:.2f}")

        # === 规则5：高宜人性 - 降低对抗性意图优先级 ===
        if agreeableness > 0.7:
            if action_type in ("confront", "compete", "argue"):
                intent["urgency"] = intent.get("urgency", 0.5) * 0.6  # 削弱40%
                logger.info(f"[PersonalityFilter] 削弱对抗意图 (高宜人): urgency -> {intent['urgency']:.2f}")

        # === 规则6：极端内向 - 避免主动发起行动 ===
        if extraversion < 0.2:
            if action_type in ("greet", "invite", "propose"):
                intent["urgency"] = intent.get("urgency", 0.5) * 0.4

        # === 规则7：极高开放性 - 鼓励探索和创新 ===
        if openness > 0.8:
            if action_type in ("exploration", "try_new", "experiment"):
                intent["urgency"] = min(1.0, intent.get("urgency", 0.5) * 1.4)

        # === 规则8：低尽责性 - 降低工作类意图优先级 ===
        if conscientiousness < 0.3:
            if action_type in ("work", "practice_skill", "study"):
                intent["urgency"] = intent.get("urgency", 0.5) * 0.7

        # === 规则9：极高神经质 - 增加担忧标签 ===
        if neuroticism > 0.8:
            intent["worry"] = True
            # 增加犹豫标签
            if action_type not in ("wait", "observe"):
                intent["hesitant"] = True

        return intent

    def filter_batch(self, intents: list[dict]) -> list[dict]:
        """
        批量过滤意图列表

        Args:
            intents: 意图列表

        Returns:
            通过过滤的意图列表（按 urgency 排序）
        """
        filtered = []
        for intent in intents:
            result = self.filter(intent.copy())
            if result is not None:
                filtered.append(result)

        # 按 urgency 排序
        filtered.sort(key=lambda x: x.get("urgency", 0), reverse=True)
        return filtered

    def get_action_style(self) -> dict:
        """
        获取性格影响下的行动风格描述（用于 Prompt）

        Returns:
            行动风格字典
        """
        extraversion = self._personality.get("extraversion", 0.5)
        openness = self._personality.get("openness", 0.5)
        conscientiousness = self._personality.get("conscientiousness", 0.5)
        agreeableness = self._personality.get("agreeableness", 0.5)
        neuroticism = self._personality.get("neuroticism", 0.5)

        style = []

        if extraversion < 0.3:
            style.append("倾向于独处，不主动与人交流")
        elif extraversion > 0.7:
            style.append("主动寻求社交，喜欢与人互动")

        if openness < 0.3:
            style.append("偏好熟悉的环境，不轻易尝试新事物")
        elif openness > 0.7:
            style.append("喜欢探索新事物，对未知充满好奇")

        if conscientiousness < 0.3:
            style.append("日程松散，容易分心")
        elif conscientiousness > 0.7:
            style.append("严格按照计划行动，有很强的时间观念")

        if agreeableness > 0.7:
            style.append("乐于合作，愿意帮助他人")
        elif agreeableness < 0.3:
            style.append("竞争性强，更关注自身利益")

        if neuroticism > 0.6:
            style.append("容易焦虑，对安全问题格外敏感")

        return {"style_description": "；".join(style) if style else "行为稳定"}