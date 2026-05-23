"""
daily_planner.py — V0.7 每日日程规划器
根据角色职业、性格生成每日日程模板，动态调整
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeBlock:
    """时间段块"""
    period: str          # morning / afternoon / evening / night
    start_hour: int       # 开始小时（游戏内时间）
    end_hour: int        # 结束小时
    activities: list      # 可选活动列表


@dataclass
class RoutineEntry:
    """日程条目"""
    period: str           # morning / afternoon / evening / night
    activity_type: str     # maintenance / goal_work / social / exploration / work / leisure
    description: str       # 活动描述
    probability: float     # 执行概率（0.0-1.0），1.0表示总是执行


class DailyPlanner:
    """
    每日日程规划器
    根据角色职业、性格、当前目标生成日程
    """

    def __init__(self, agent_id: str):
        self._agent_id = agent_id
        self._routine: list[RoutineEntry] = []
        self._current_period = "morning"

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def routine(self) -> list[RoutineEntry]:
        return self._routine.copy()

    def generate_daily_routine(
        self,
        personality: dict,
        occupation: str = None,
        active_goal: str = None,
        goal_type: str = None,
        game_hour: int = 8
    ) -> list[RoutineEntry]:
        """
        生成每日日程

        Args:
            personality: Big Five 性格参数
            occupation: 职业（影响日程内容）
            active_goal: 当前活跃目标描述
            goal_type: 目标类型（mastery/social/exploration/maintenance）
            game_hour: 当前游戏内小时（用于确定当前时段）

        Returns:
            日程条目列表
        """
        self._routine = []
        extraversion = personality.get("extraversion", 0.5)
        openness = personality.get("openness", 0.5)
        conscientiousness = personality.get("conscientiousness", 0.5)

        # === Morning (6-10) ===
        self._routine.append(RoutineEntry(
            period="morning",
            activity_type="maintenance",
            description="起床整理，查看环境",
            probability=1.0
        ))

        # 如果有目标驱动的工作，在上午执行
        if active_goal and goal_type in ("mastery", "maintenance"):
            self._routine.append(RoutineEntry(
                period="morning",
                activity_type="goal_work",
                description=f"推进目标：{active_goal}",
                probability=0.9
            ))
        else:
            self._routine.append(RoutineEntry(
                period="morning",
                activity_type="work",
                description=self._get_occupation_activity(occupation, "morning"),
                probability=0.8
            ))

        # === Afternoon (10-18) ===
        if active_goal and goal_type == "social":
            self._routine.append(RoutineEntry(
                period="afternoon",
                activity_type="social",
                description=f"与他人互动：{active_goal}",
                probability=0.85
            ))
        elif active_goal and goal_type == "exploration":
            self._routine.append(RoutineEntry(
                period="afternoon",
                activity_type="exploration",
                description=f"探索：{active_goal}",
                probability=0.7 + (openness * 0.3)
            ))
        else:
            # 高外向性增加社交概率
            if extraversion > 0.5:
                self._routine.append(RoutineEntry(
                    period="afternoon",
                    activity_type="social",
                    description="与周围的人交流",
                    probability=0.4 + (extraversion * 0.3)
                ))

            self._routine.append(RoutineEntry(
                period="afternoon",
                activity_type="work",
                description=self._get_occupation_activity(occupation, "afternoon"),
                probability=0.75
            ))

        # === Evening (18-22) ===
        # 高尽责性倾向于继续工作，低外向性倾向于独处
        if conscientiousness > 0.6 and active_goal:
            self._routine.append(RoutineEntry(
                period="evening",
                activity_type="goal_work",
                description=f"继续推进目标",
                probability=0.6
            ))
        else:
            self._routine.append(RoutineEntry(
                period="evening",
                activity_type="leisure",
                description="休息放松，整理一天的经历",
                probability=0.8
            ))

            # 高外向性可能社交
            if extraversion > 0.6:
                self._routine.append(RoutineEntry(
                    period="evening",
                    activity_type="social",
                    description="在公共场所与人交流",
                    probability=0.3 + (extraversion * 0.2)
                ))

        # === Night (22-6) ===
        self._routine.append(RoutineEntry(
            period="night",
            activity_type="rest",
            description="休息睡眠",
            probability=1.0
        ))

        # 更新当前时段
        self._current_period = self._get_period_for_hour(game_hour)

        logger.info(f"[DailyPlanner] [{self._agent_id}] 生成了 {len(self._routine)} 条日程")
        return self._routine

    def _get_occupation_activity(self, occupation: str, period: str) -> str:
        """根据职业获取活动描述"""
        if not occupation:
            return "进行日常工作"

        activities = {
            "scholar": {
                "morning": "在书房阅读研究",
                "afternoon": "整理笔记，撰写文章",
                "evening": "查阅资料",
            },
            "merchant": {
                "morning": "清点货物",
                "afternoon": "经营店铺",
                "evening": "记账整理",
            },
            "artisan": {
                "morning": "准备工具材料",
                "afternoon": "制作手工艺品",
                "evening": "打磨作品",
            },
            "guard": {
                "morning": "巡逻检查",
                "afternoon": "驻守岗位",
                "evening": "交接班",
            },
            "healer": {
                "morning": "整理药材",
                "afternoon": "治疗病患",
                "evening": "研磨草药",
            },
        }

        occ_activities = activities.get(occupation.lower(), {})
        return occ_activities.get(period, "进行日常工作")

    def _get_period_for_hour(self, hour: int) -> str:
        """根据小时获取时段"""
        if 6 <= hour < 10:
            return "morning"
        elif 10 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"

    def get_current_activity(self, game_hour: int = None) -> RoutineEntry:
        """
        获取当前时段应执行的日程

        Args:
            game_hour: 游戏内小时，如果为None则使用当前记录的时段

        Returns:
            当前应执行的活动条目
        """
        if game_hour is not None:
            self._current_period = self._get_period_for_hour(game_hour)
        else:
            # 根据时间推进时段
            pass

        # 查找当前时段的活动
        for entry in self._routine:
            if entry.period == self._current_period and entry.probability >= 0.5:
                return entry

        # 默认返回维护活动
        return RoutineEntry(
            period=self._current_period,
            activity_type="maintenance",
            description="例行活动",
            probability=1.0
        )

    def get_activity_for_period(self, period: str) -> list[RoutineEntry]:
        """获取指定时段的所有活动"""
        return [e for e in self._routine if e.period == period]

    def adjust_for_event(self, event_description: str, priority: str = "medium"):
        """
        根据突发事件调整日程

        Args:
            event_description: 事件描述
            priority: 优先级（high / medium / low）
        """
        if priority == "high":
            # 高优先级事件替换当前活动
            self._routine.insert(0, RoutineEntry(
                period=self._current_period,
                activity_type="urgent",
                description=f"处理紧急事件：{event_description}",
                probability=1.0
            ))
            logger.info(f"[DailyPlanner] [{self._agent_id}] 插入紧急事件: {event_description}")
        else:
            # 中低优先级添加到最后
            self._routine.append(RoutineEntry(
                period=self._current_period,
                activity_type="opportunity",
                description=f"抓住机会：{event_description}",
                probability=0.6
            ))

    def sync_hour(self, game_hour: int):
        """同步游戏时间"""
        self._current_period = self._get_period_for_hour(game_hour)