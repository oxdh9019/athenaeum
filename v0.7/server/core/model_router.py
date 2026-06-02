"""
model_router.py — V0.7 模型路由器
根据意图类型、附身状态和预算决定使用哪个模型
"""

import logging
from dataclasses import replace
from datetime import datetime, date
from typing import Optional

from .interfaces import IModelRouter, RouterStats, IntentType
from .plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

# 意图类型到路由目标的映射
LOCAL_INTENTS = {"greet", "ask", "wait", "move"}
CLOUD_INTENTS = {"share", "invite", "flee", "confess"}
# 这些任务不降级
NO_DEGRADE_INTENTS = {"summarize", "narrate", "world_generate"}


class ModelRouter(IModelRouter):
    """
    模型路由器
    根据意图类型、附身状态和预算决定使用本地还是云端模型
    """

    def __init__(
        self,
        daily_budget: float = 10.0,
        degrade_threshold: float = 0.8,
        emergency_threshold: float = 0.95,
    ):
        """
        Args:
            daily_budget: 每日预算（美元）
            degrade_threshold: 降级阈值（预算使用比例）
            emergency_threshold: 紧急降级阈值（即使附身也降级）
        """
        self._daily_budget = daily_budget
        self._degrade_threshold = degrade_threshold
        self._emergency_threshold = emergency_threshold

        self._stats = RouterStats(
            local_calls=0,
            cloud_calls=0,
            degrade_active=False,
            budget_remaining=1.0,
            budget_ratio=0.0,
            daily_budget=daily_budget,
            last_reset=datetime.now(),
            total_cost=0.0,
        )

        self._today = date.today()

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
        intent = intent_type.lower()

        # 不降级的任务
        if intent in NO_DEGRADE_INTENTS:
            return "cloud"

        # 紧急降级：预算超 95%，即使附身也降级
        if budget_ratio >= self._emergency_threshold:
            logger.info(f"[Router] 预算紧急降级: ratio={budget_ratio:.2%}, intent={intent}")
            self._stats.degrade_active = True
            return "local"

        # 普通降级：预算超 80%，非附身请求降级
        if budget_ratio >= self._degrade_threshold and not is_possessed:
            logger.info(f"[Router] 预算降级: ratio={budget_ratio:.2%}, intent={intent}")
            self._stats.degrade_active = True
            return "local"

        # 默认规则
        if intent in LOCAL_INTENTS:
            return "local"
        elif intent in CLOUD_INTENTS:
            return "cloud"

        # 未知意图，根据附身状态决定
        if is_possessed:
            return "cloud"
        return "local"

    def get_stats(self) -> RouterStats:
        """返回路由统计（防御性副本，防止调用方意外修改内部状态）"""
        self._check_daily_reset()
        return replace(self._stats)

    def record_call(self, model: str, tokens: int, cost: float):
        """
        记录一次调用（用于成本统计）

        Args:
            model: "local" 或 "cloud"
            tokens: 使用的 token 数
            cost: 费用（美元）
        """
        self._check_daily_reset()

        # 防御性归一化：未知 model 名称一律视为 local（不会错算到云端）
        # 这避免上游误传 "qwen3.5:4b" 这种模型名字时被错误计入 cloud_calls
        if model not in ("local", "cloud"):
            logger.debug(f"[Router] 收到非标准 model 名称 {model!r}，归一化为 local")
            model = "local"

        if model == "local":
            self._stats.local_calls += 1
        else:
            self._stats.cloud_calls += 1
            # 防御：cost 不应为负
            cost = max(0.0, float(cost))
            self._stats.total_cost += cost

        self._stats.budget_ratio = self._stats.total_cost / self._daily_budget
        self._stats.budget_remaining = max(0, 1.0 - self._stats.budget_ratio)

        # 更新降级状态
        self._stats.degrade_active = self._stats.budget_ratio >= self._degrade_threshold

        logger.debug(f"[Router] 记录调用: model={model}, tokens={tokens}, cost=${cost:.4f}, budget_ratio={self._stats.budget_ratio:.2%}")

    def reset_daily_budget(self):
        """重置每日预算（每日 00:00 调用）"""
        self._stats.local_calls = 0
        self._stats.cloud_calls = 0
        self._stats.total_cost = 0.0
        self._stats.budget_ratio = 0.0
        self._stats.budget_remaining = 1.0
        self._stats.degrade_active = False
        self._stats.last_reset = datetime.now()
        self._today = date.today()
        logger.info("[Router] 每日预算已重置")

    def _check_daily_reset(self):
        """检查是否需要每日重置"""
        today = date.today()
        if today > self._today:
            self.reset_daily_budget()

    def set_budget(self, daily_budget: float):
        """设置每日预算"""
        self._daily_budget = daily_budget
        self._stats.daily_budget = daily_budget

    def get_model_for_intent(self, intent_type: str, is_possessed: bool = False) -> str:
        """
        便捷方法：获取意图对应的模型（内部使用）

        等同于 route() 但返回模型名称而非 "local"/"cloud"
        """
        model_key = self.route(intent_type, is_possessed, self._stats.budget_ratio)

        if model_key == "local":
            return "local"
        return "cloud"


def create_default_router() -> ModelRouter:
    """创建默认路由器实例（带注册）"""
    router = ModelRouter()
    PluginRegistry.register_router("default", router)
    return router