"""
goal_manager.py — V0.7 目标管理器
管理单个角色的目标队列、进度、生命周期
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class GoalType(Enum):
    MASTERY = "mastery"      # 技能提升
    SOCIAL = "social"        # 社交
    EXPLORATION = "exploration"  # 探索
    MAINTENANCE = "maintenance"  # 日常维护


class GoalStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class Goal:
    """目标数据结构"""
    goal_id: str
    agent_id: str
    goal_type: GoalType
    description: str
    progress: float = 0.0  # 0.0 - 1.0
    priority: float = 0.5  # 0.0 - 1.0
    deadline_tick: Optional[int] = None
    sub_tasks: list[str] = field(default_factory=list)
    status: GoalStatus = GoalStatus.PENDING
    created_tick: int = 0

    def mark_active(self):
        self.status = GoalStatus.ACTIVE

    def complete(self):
        self.status = GoalStatus.COMPLETED
        self.progress = 1.0


class GoalManager:
    """
    目标管理器
    管理角色的目标队列，支持从 Soul 配置生成目标
    """

    def __init__(self, agent_id: str, personality: dict = None):
        self._agent_id = agent_id
        self._personality = personality or {}
        self._goals: list[Goal] = []
        self._active_goal: Optional[Goal] = None
        self._tick_count = 0

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def active_goal(self) -> Optional[Goal]:
        return self._active_goal

    @property
    def all_goals(self) -> list[Goal]:
        return self._goals.copy()

    @property
    def active_goals(self) -> list[Goal]:
        return [g for g in self._goals if g.status == GoalStatus.ACTIVE]

    def set_personality(self, personality: dict):
        self._personality = personality

    def sync_tick(self, current_tick: int):
        """同步当前 tick"""
        self._tick_count = current_tick

    async def generate_goals_from_soul(
        self,
        soul: dict,
        personality: dict,
        current_location: str = None,
        existing_relationships: list = None
    ) -> list[Goal]:
        """
        从 Soul 配置生成目标列表

        Args:
            soul: Soul 配置，包含 core_desires, long_term_goals, behavioral_tendencies
            personality: Big Five 性格参数
            current_location: 当前地点（影响目标生成）
            existing_relationships: 已有关系列表

        Returns:
            生成的目标列表
        """
        goals = []
        agent_id = self._agent_id

        # 1. 从 core_desires 生成深层目标
        core_desires = soul.get("core_desires", [])
        for desire in core_desires:
            goal = self._create_goal_from_desire(
                agent_id, desire, personality, GoalType.MASTERY
            )
            if goal:
                goals.append(goal)

        # 2. 从 long_term_goals 生成中期目标
        long_term_goals = soul.get("long_term_goals", [])
        for ltg in long_term_goals:
            goal = self._create_goal_from_ltg(agent_id, ltg, personality)
            if goal:
                goals.append(goal)

        # 3. 生成日常维护目标
        maintenance_goal = self._generate_maintenance_goal(
            agent_id, personality, current_location
        )
        if maintenance_goal:
            goals.append(maintenance_goal)

        # 4. 基于关系生成社交目标
        if existing_relationships:
            for rel in existing_relationships[:2]:  # 最多2个社交目标
                if isinstance(rel, dict) and rel.get("strength", 0) > 0.3:
                    social_goal = self._create_social_goal(agent_id, rel, personality)
                    if social_goal:
                        goals.append(social_goal)

        # 添加到目标队列
        for goal in goals:
            self._goals.append(goal)

        # 设置最高优先级目标为活跃
        self._activate_top_goal()

        logger.info(f"[GoalManager] [{agent_id}] 生成了 {len(goals)} 个目标")
        return goals

    def _create_goal_from_desire(
        self, agent_id: str, desire: dict, personality: dict, goal_type: GoalType
    ) -> Optional[Goal]:
        """从 core_desire 创建目标"""
        desire_name = desire.get("name", "") if isinstance(desire, dict) else str(desire)
        level = desire.get("level", 0.5) if isinstance(desire, dict) else 0.5

        # 根据性格调整优先级
        priority = level
        if personality.get("conscientiousness", 0.5) > 0.6:
            priority *= 1.2  # 高尽责性更重视目标

        goal_id = f"goal_{agent_id}_{desire_name}_{self._tick_count}"
        description = f"追求{desire_name}"

        return Goal(
            goal_id=goal_id,
            agent_id=agent_id,
            goal_type=goal_type,
            description=description,
            priority=min(1.0, priority),
            deadline_tick=self._tick_count + 50,  # 默认50 tick内完成
            created_tick=self._tick_count,
        )

    def _create_goal_from_ltg(
        self, agent_id: str, ltg: dict, personality: dict
    ) -> Optional[Goal]:
        """从 long_term_goal 创建目标"""
        if isinstance(ltg, str):
            description = ltg
        elif isinstance(ltg, dict):
            description = ltg.get("description", "长期目标")
        else:
            return None

        # 推断目标类型
        goal_type = GoalType.MASTERY
        if any(kw in description for kw in ["朋友", "社交", "关系", "拜访"]):
            goal_type = GoalType.SOCIAL
        elif any(kw in description for kw in ["探索", "发现", "去"]):
            goal_type = GoalType.EXPLORATION

        goal_id = f"goal_{agent_id}_ltg_{self._tick_count}"
        priority = 0.6 + (personality.get("openness", 0.5) * 0.2)

        return Goal(
            goal_id=goal_id,
            agent_id=agent_id,
            goal_type=goal_type,
            description=description,
            priority=min(1.0, priority),
            deadline_tick=self._tick_count + 100,
            created_tick=self._tick_count,
        )

    def _generate_maintenance_goal(
        self, agent_id: str, personality: dict, location: str = None
    ) -> Goal:
        """生成日常维护目标"""
        loc_desc = f"在{location}" if location else "当前地点"
        description = f"完成日常任务：整理环境、准备所需"

        goal_id = f"goal_{agent_id}_maint_{self._tick_count}"
        return Goal(
            goal_id=goal_id,
            agent_id=agent_id,
            goal_type=GoalType.MAINTENANCE,
            description=description,
            priority=0.5,
            deadline_tick=self._tick_count + 20,
            created_tick=self._tick_count,
        )

    def _create_social_goal(
        self, agent_id: str, relationship: dict, personality: dict
    ) -> Optional[Goal]:
        """基于关系创建社交目标"""
        target_id = relationship.get("to_id") or relationship.get("target", "")
        if not target_id:
            return None

        description = f"与{target_id}交流"
        goal_id = f"goal_{agent_id}_social_{target_id}_{self._tick_count}"

        # 高外向性更重视社交目标
        extraversion = personality.get("extraversion", 0.5)
        priority = 0.4 + (extraversion * 0.4)

        return Goal(
            goal_id=goal_id,
            agent_id=agent_id,
            goal_type=GoalType.SOCIAL,
            description=description,
            priority=min(1.0, priority),
            deadline_tick=self._tick_count + 30,
            created_tick=self._tick_count,
        )

    def _activate_top_goal(self):
        """激活最高优先级的目标"""
        active_goals = [g for g in self._goals if g.status == GoalStatus.PENDING]
        if not active_goals:
            return

        # 按优先级排序
        active_goals.sort(key=lambda g: g.priority, reverse=True)
        top_goal = active_goals[0]
        top_goal.mark_active()
        self._active_goal = top_goal
        logger.info(f"[GoalManager] [{self._agent_id}] 激活目标: {top_goal.description}")

    async def update_goal_progress(self, goal_id: str, progress_delta: float) -> bool:
        """
        更新目标进度

        Args:
            goal_id: 目标ID
            progress_delta: 进度增量（0.0 - 1.0）

        Returns:
            是否触发目标完成
        """
        goal = self._find_goal(goal_id)
        if not goal:
            return False

        old_progress = goal.progress
        goal.progress = min(1.0, goal.progress + progress_delta)

        logger.info(
            f"[GoalManager] [{self._agent_id}] 进度更新: {goal.description} "
            f"{old_progress:.0%} → {goal.progress:.0%}"
        )

        # 检查是否完成
        if goal.progress >= 1.0:
            await self._on_goal_completed(goal)
            return True

        return False

    def _find_goal(self, goal_id: str) -> Optional[Goal]:
        """查找目标"""
        for goal in self._goals:
            if goal.goal_id == goal_id:
                return goal
        return None

    async def _on_goal_completed(self, goal: Goal):
        """
        目标完成后的连锁反应

        1. 标记完成
        2. 降低相关需求
        3. 激活下一个目标
        """
        goal.complete()
        logger.info(f"[GoalManager] [{self._agent_id}] 目标完成: {goal.description}")

        # 如果完成的是当前活跃目标，激活下一个
        if self._active_goal and self._active_goal.goal_id == goal.goal_id:
            self._active_goal = None
            self._activate_top_goal()

    def get_current_intent(self) -> dict:
        """
        获取当前意图描述（用于 decide_action 的 Prompt）

        Returns:
            包含活跃目标描述的字典
        """
        if self._active_goal:
            return {
                "active_goal": self._active_goal.description,
                "goal_type": self._active_goal.goal_type.value,
                "goal_progress": self._active_goal.progress,
                "goal_priority": self._active_goal.priority,
            }

        # 无活跃目标时返回日常
        return {
            "active_goal": "无特定目标，执行日常活动",
            "goal_type": "maintenance",
            "goal_progress": 0.0,
            "goal_priority": 0.3,
        }

    def add_sub_task(self, goal_id: str, task: str):
        """为目标添加子任务"""
        goal = self._find_goal(goal_id)
        if goal and task not in goal.sub_tasks:
            goal.sub_tasks.append(task)

    def get_pending_count(self) -> int:
        """获取待处理目标数量"""
        return len([g for g in self._goals if g.status == GoalStatus.PENDING])

    def clear_completed(self):
        """清除已完成目标（保留最近N个）"""
        completed = [g for g in self._goals if g.status == GoalStatus.COMPLETED]
        # 保留最近3个已完成目标用于记忆
        for goal in completed[3:]:
            self._goals.remove(goal)