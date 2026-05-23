"""
story_mode.py — V0.7 故事模式与结束检测
管理有限 Tick 的故事运行，检测结束条件，生成故事摘要
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class StoryStatus(Enum):
    """故事状态"""
    IDLE = "idle"
    RUNNING = "running"
    ENDING = "ending"
    ENDED = "ended"


@dataclass
class StoryConfig:
    """故事配置"""
    max_ticks: int = 200          # 最大 Tick 数
    min_ticks: int = 50          # 最小 Tick 数
    end_keywords: list = None     # 结束关键词列表
    auto_end_threshold: float = 0.8  # 自动结束阈值

    def __post_init__(self):
        if self.end_keywords is None:
            self.end_keywords = [
                "告别", "离开", "结束", "晚安", "再见",
                "farewell", "goodbye", "end"
            ]


@dataclass
class StoryEvent:
    """故事事件"""
    tick: int
    event_type: str           # "dialogue" / "action" / "relationship_change" / "narrative"
    description: str
    participants: list = field(default_factory=list)
    emotion: str = "neutral"


class StoryMode:
    """
    故事模式控制器

    功能:
    - 管理有限 Tick 的故事运行
    - 检测连续 N Tick 无高优先级目标、离开关键词等，触发收尾
    - 结束时生成故事摘要
    """

    def __init__(
        self,
        story_id: str,
        config: StoryConfig = None,
        llm=None,
    ):
        self._story_id = story_id
        self._config = config or StoryConfig()
        self._llm = llm

        self._status = StoryStatus.IDLE
        self._start_tick: int = 0
        self._current_tick: int = 0
        self._tick_limit: int = self._config.max_ticks

        # 事件记录
        self._events: list[StoryEvent] = []

        # 连续低活动计数
        self._low_activity_ticks: int = 0
        self._high_priority_goal_ticks: int = 0

        # 完成回调
        self._on_end_callback: Optional[Callable] = None

        # 故事摘要
        self._summary: Optional[str] = None

    @property
    def story_id(self) -> str:
        return self._story_id

    @property
    def status(self) -> StoryStatus:
        return self._status

    @property
    def current_tick(self) -> int:
        return self._current_tick

    @property
    def summary(self) -> Optional[str]:
        return self._summary

    def start(self, start_tick: int, tick_limit: int = None):
        """开始故事"""
        self._status = StoryStatus.RUNNING
        self._start_tick = start_tick
        self._current_tick = start_tick
        self._tick_limit = tick_limit or self._config.max_ticks
        self._events = []
        self._low_activity_ticks = 0
        self._high_priority_goal_ticks = 0
        self._summary = None

        logger.info(
            f"[StoryMode] [{self._story_id}] 故事开始: "
            f"tick={start_tick}, limit={self._tick_limit}"
        )

    def set_end_callback(self, callback: Callable):
        """设置结束回调"""
        self._on_end_callback = callback

    def tick_update(
        self,
        current_tick: int,
        active_goals: list = None,
        recent_dialogues: list = None,
        relationship_changes: list = None,
    ) -> bool:
        """
        每 Tick 更新，检查是否应结束

        Args:
            current_tick: 当前 Tick
            active_goals: 当前活跃目标列表
            recent_dialogues: 最近对话列表
            relationship_changes: 最近关系变化列表

        Returns:
            True = 故事应该结束，False = 继续
        """
        if self._status != StoryStatus.RUNNING:
            return False

        self._current_tick = current_tick

        # 检查最大 Tick 限制
        if current_tick - self._start_tick >= self._tick_limit:
            logger.info(f"[StoryMode] [{self._story_id}] 达到最大 Tick 数，结束故事")
            return self._trigger_end("max_ticks_reached")

        # 检查最小 Tick 数
        ticks_running = current_tick - self._start_tick
        if ticks_running < self._config.min_ticks:
            return False

        # 检查高优先级目标
        has_high_priority_goal = False
        if active_goals:
            for goal in active_goals:
                priority = getattr(goal, 'priority', 0)
                if priority > 0.8:
                    has_high_priority_goal = True
                    break

        if has_high_priority_goal:
            self._high_priority_goal_ticks += 1
            self._low_activity_ticks = 0
        else:
            self._high_priority_goal_ticks = 0
            self._low_activity_ticks += 1

        # 检查结束关键词（对话中）
        if recent_dialogues:
            for dialogue in recent_dialogues[-5:]:
                utterance = dialogue.get("utterance", "").lower()
                for keyword in self._config.end_keywords:
                    if keyword.lower() in utterance:
                        logger.info(
                            f"[StoryMode] [{self._story_id}] 检测到结束关键词: {keyword}"
                        )
                        return self._trigger_end("end_keyword_detected")

        # 检查连续低活动（无高优先级目标）
        if self._low_activity_ticks >= 15:
            logger.info(
                f"[StoryMode] [{self._story_id}] 连续 {self._low_activity_ticks} Tick 无高优先级目标"
            )
            return self._trigger_end("low_activity_timeout")

        # 检查关系变化幅度（戏剧性事件后）
        if relationship_changes:
            total_change = sum(abs(c) for c in relationship_changes[-5:] if isinstance(c, (int, float)))
            if total_change > 0.5:
                logger.info(
                    f"[StoryMode] [{self._story_id}] 检测到显著关系变化: {total_change:.2f}"
                )
                # 戏剧性事件后，观察一段时间再决定是否结束
                pass

        return False

    def _trigger_end(self, reason: str) -> bool:
        """触发故事结束"""
        self._status = StoryStatus.ENDING
        logger.info(f"[StoryMode] [{self._story_id}] 故事结束原因: {reason}")

        # 异步生成摘要
        asyncio.create_task(self._generate_summary())

        return True

    async def _generate_summary(self):
        """生成故事摘要"""
        if not self._llm:
            self._summary = self._generate_simple_summary()
            self._finish_end()
            return

        try:
            # 构建故事事件摘要
            event_summary = []
            for event in self._events[-20:]:
                event_summary.append(f"[Tick {event.tick}] {event.description}")

            prompt = f"""请为以下故事生成一段简洁的摘要（100-200字）：

故事ID: {self._story_id}
运行 Tick: {self._current_tick - self._start_tick}

主要事件：
{chr(10).join(event_summary) if event_summary else "（无记录事件）"}

请总结：
1. 故事的主要情节
2. 角色之间的关系变化
3. 故事的主题或意义

请用中文输出。"""

            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500,
            )

            self._summary = response.strip()
            logger.info(f"[StoryMode] [{self._story_id}] 摘要生成完成")

        except Exception as e:
            logger.error(f"[StoryMode] [{self._story_id}] 摘要生成失败: {e}")
            self._summary = self._generate_simple_summary()

        self._finish_end()

    def _generate_simple_summary(self) -> str:
        """生成简单摘要（无 LLM）"""
        dialogue_count = len([e for e in self._events if e.event_type == "dialogue"])
        action_count = len([e for e in self._events if e.event_type == "action"])

        return (
            f"故事 {self._story_id} 结束。"
            f"运行 {self._current_tick - self._start_tick} Tick，"
            f"包含 {dialogue_count} 次对话，{action_count} 次动作。"
        )

    def _finish_end(self):
        """完成结束流程"""
        self._status = StoryStatus.ENDED

        if self._on_end_callback:
            try:
                self._on_end_callback(self._story_id, self._summary)
            except Exception as e:
                logger.error(f"[StoryMode] [{self._story_id}] 结束回调执行失败: {e}")

        logger.info(f"[StoryMode] [{self._story_id}] 故事已结束")

    def record_event(self, event: StoryEvent):
        """记录故事事件"""
        self._events.append(event)

        if len(self._events) > 500:
            # 保留最近 500 个事件
            self._events = self._events[-500:]

    def record_dialogue(self, tick: int, from_name: str, to_name: str, utterance: str, emotion: str = "neutral"):
        """便捷方法：记录对话事件"""
        self.record_event(StoryEvent(
            tick=tick,
            event_type="dialogue",
            description=f"{from_name} 对 {to_name} 说: {utterance[:50]}...",
            participants=[from_name, to_name],
            emotion=emotion,
        ))

    def record_action(self, tick: int, agent_name: str, action: str):
        """便捷方法：记录动作事件"""
        self.record_event(StoryEvent(
            tick=tick,
            event_type="action",
            description=f"{agent_name} {action}",
            participants=[agent_name],
        ))

    def record_relationship_change(
        self,
        tick: int,
        agent_a: str,
        agent_b: str,
        change: float
    ):
        """便捷方法：记录关系变化"""
        direction = "加深" if change > 0 else "减弱"
        self.record_event(StoryEvent(
            tick=tick,
            event_type="relationship_change",
            description=f"{agent_a} 和 {agent_b} 的关系{direction}（Δ={change:+.2f}）",
            participants=[agent_a, agent_b],
        ))

    def get_status(self) -> dict:
        """获取状态"""
        return {
            "story_id": self._story_id,
            "status": self._status.value,
            "current_tick": self._current_tick,
            "ticks_running": self._current_tick - self._start_tick,
            "tick_limit": self._tick_limit,
            "event_count": len(self._events),
            "low_activity_ticks": self._low_activity_ticks,
            "has_summary": self._summary is not None,
        }


class StoryManager:
    """
    故事管理器 - 管理多个故事实例
    """

    def __init__(self, llm=None):
        self._llm = llm
        self._stories: dict[str, StoryMode] = {}
        self._story_counter: int = 0

    def create_story(
        self,
        max_ticks: int = 200,
        min_ticks: int = 50,
        tick_limit: int = None,
    ) -> StoryMode:
        """
        创建新故事

        Args:
            max_ticks: 最大 Tick 数
            min_ticks: 最小 Tick 数
            tick_limit: 具体的 Tick 上限（覆盖 max_ticks）

        Returns:
            StoryMode 实例
        """
        self._story_counter += 1
        story_id = f"story_{self._story_counter}"

        config = StoryConfig(
            max_ticks=tick_limit or max_ticks,
            min_ticks=min_ticks,
        )

        story = StoryMode(
            story_id=story_id,
            config=config,
            llm=self._llm,
        )

        self._stories[story_id] = story
        logger.info(f"[StoryManager] 创建故事: {story_id}")

        return story

    def get_story(self, story_id: str) -> Optional[StoryMode]:
        """获取故事实例"""
        return self._stories.get(story_id)

    def end_story(self, story_id: str) -> bool:
        """手动结束故事"""
        story = self._stories.get(story_id)
        if not story:
            return False

        if story.status == StoryStatus.RUNNING:
            return story._trigger_end("manual_end")

        return False

    def list_stories(self) -> list[dict]:
        """列出所有故事"""
        return [s.get_status() for s in self._stories.values()]

    def cleanup_ended_stories(self, max_age_ticks: int = 100):
        """清理已结束的故事（保留最近 N Tick）"""
        to_remove = []
        for story_id, story in self._stories.items():
            if story.status == StoryStatus.ENDED:
                age = story.current_tick - story._start_tick
                if age > max_age_ticks:
                    to_remove.append(story_id)

        for story_id in to_remove:
            self._stories.pop(story_id)
            logger.info(f"[StoryManager] 清理已结束故事: {story_id}")