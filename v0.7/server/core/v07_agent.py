"""
agent.py — V0.7 Agent 实现（拟人化模式）
V0.5 记忆系统 + V0.7 欲望→目标→行动 三层驱动模型
"""

import asyncio
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class V07Agent:
    """
    V0.7 Agent - 封装角色行为、决策和记忆系统
    集成：短期记忆、长期记忆归档、语义检索、遗忘曲线
          目标管理、日程规划、情绪模型、性格过滤、心跳模式
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        personality: dict,
        occupation: str,
        soul: dict,
        llm,
        world,
        initial_location: str,
        cloud_llm=None,
        local_llm=None,
        archiver=None,
        retriever=None,
        forgetting_curve=None,
    ):
        self._agent_id = agent_id
        self._name = name
        self._personality = personality
        self._occupation = occupation
        self._soul = soul or {}
        self._llm = llm
        self._cloud_llm = cloud_llm
        self._local_llm = local_llm
        self._world = world
        self._current_location = initial_location

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # 短期记忆（V0.3 原有）
        self._short_term_memory: list[tuple[str, str]] = []
        self._max_memory = 20

        # V0.5 记忆系统
        self._archiver = archiver
        self._retriever = retriever
        self._forgetting_curve = forgetting_curve

        # 对话归档缓冲
        self._dialogue_buffer: list[dict] = []

        # ========== V0.7 拟人化组件 ==========

        # 目标管理器
        from .goal_manager import GoalManager
        self._goal_manager = GoalManager(agent_id, personality)
        if soul:
            existing_rels = getattr(self, '_relationships', [])
            asyncio.create_task(
                self._goal_manager.generate_goals_from_soul(
                    soul, personality, initial_location, existing_rels
                )
            )

        # 日程规划器
        from .daily_planner import DailyPlanner
        self._daily_planner = DailyPlanner(agent_id)
        self._sync_daily_plan()

        # 情绪模型
        from .emotion_model import EmotionModel
        self._emotion_model = EmotionModel(agent_id, initial_valence=0.0, initial_arousal=0.3)

        # 性格过滤器
        from .personality_filter import PersonalityFilter
        self._personality_filter = PersonalityFilter(personality)

        # 心跳模式
        from .heartbeat_mode import HeartbeatMode, HeartbeatConfig
        config = HeartbeatConfig(enabled=True, base_interval=10)
        self._heartbeat_mode = HeartbeatMode(agent_id, personality, config)

        # V0.7: 潜意识引擎
        from .subconscious_engine import SubconsciousEngine, SoulConfig
        soul_config = SoulConfig.from_dict(soul) if soul else SoulConfig()
        self._subconscious_engine = SubconsciousEngine(agent_id, soul_config)

        # V0.7: 目标管理器关联组件
        self._goal_manager.set_emotion_model(self._emotion_model)
        self._goal_manager.set_dialogue_callback(self._on_goal_share)

    def _sync_daily_plan(self):
        """同步日程计划"""
        active_goal = self._goal_manager.active_goal
        goal_type = active_goal.goal_type.value if active_goal else None
        current_hour = 8  # 默认早上
        if hasattr(self._world, '_game_hour'):
            current_hour = self._world._game_hour

        self._daily_planner.generate_daily_routine(
            personality=self._personality,
            occupation=self._occupation,
            active_goal=active_goal.description if active_goal else None,
            goal_type=goal_type,
            game_hour=current_hour,
        )

    @property
    def id(self) -> str:
        return self._agent_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def personality(self) -> dict:
        return self._personality

    @property
    def personality_desc(self) -> str:
        lines = []
        for trait, val in self._personality.items():
            desc = "高" if val > 0.6 else "低"
            lines.append(f"{trait}: {val:.1f}（{desc}）")
        return "\n".join(lines)

    @property
    def neuroticism(self) -> float:
        return self._personality.get("neuroticism", 0.5)

    @property
    def needs(self) -> Any:
        if hasattr(self, '_needs'):
            return self._needs
        return None

    @property
    def goal_manager(self):
        return self._goal_manager

    @property
    def emotion_model(self):
        return self._emotion_model

    @property
    def heartbeat_mode(self):
        return self._heartbeat_mode

    @property
    def subconscious_engine(self):
        return self._subconscious_engine

    # ==================== 性格属性访问器 ====================

    @property
    def empathy(self) -> float:
        return self._personality.get('empathy', 0.5)

    @property
    def ambition(self) -> float:
        return self._personality.get('ambition', 0.5)

    @property
    def courage(self) -> float:
        return self._personality.get('courage', 0.5)

    @property
    def loyalty(self) -> float:
        return self._personality.get('loyalty', 0.5)

    # ==================== 系统事件接收 ====================

    def receive_system_event(self, event) -> None:
        if not hasattr(self, '_external_event_queue'):
            self._external_event_queue: list = []

        from dataclasses import dataclass
        @dataclass
        class SystemMessage:
            tick: int
            type: str
            description: str
            affected_agents: list

        message = SystemMessage(
            tick=getattr(self._world, '_tick_id', 0),
            type=getattr(event, 'event_type', 'unknown'),
            description=getattr(event, 'description', ''),
            affected_agents=getattr(event, 'participants', [])
        )
        self._external_event_queue.append(message)

        # V0.7: 事件影响情绪
        event_type = message.type
        if 'danger' in event_type.lower():
            self._emotion_model.apply_event('danger')
        elif 'positive' in event_type.lower():
            self._emotion_model.apply_event('positive_social')
        elif 'negative' in event_type.lower():
            self._emotion_model.apply_event('negative_social')
        elif 'narrative' in event_type.lower():
            self._emotion_model.apply_event('narrative', {"sentiment": 0.1})

        logger.info(f"[{self._name}] 接收系统事件: {message.type}")

    # ==================== 记忆系统 ====================

    def add_memory(self, role: str, content: str) -> None:
        self._short_term_memory.append((role, content))
        if len(self._short_term_memory) > self._max_memory:
            self._short_term_memory.pop(0)

    def get_memory_context(self) -> list[dict]:
        return [{"role": r, "content": c} for r, c in self._short_term_memory[-self._max_memory:]]

    def add_dialogue_for_archival(self, dialogue_data: dict) -> None:
        self._dialogue_buffer.append(dialogue_data)
        speaker = dialogue_data.get("from", "")
        utterance = dialogue_data.get("utterance", "")
        if speaker and utterance:
            self.add_memory(speaker, utterance)

    async def try_archive(self, current_tick: int, force: bool = False) -> None:
        if self._archiver and self._dialogue_buffer:
            pending_count = len(self._dialogue_buffer)

            # V0.7: 条件反思机制 - 计算 drama_score
            drama_score = 0.0
            if pending_count >= 5:
                drama_score = self._archiver.evaluate_drama(
                    self._agent_id,
                    self._dialogue_buffer[-10:],
                    [],  # relationship_changes
                    [],  # narrative_events
                )

            # drama_score >= 0.3 或 pending >= 10 时触发归档
            should_force = drama_score >= 0.3
            if pending_count >= 10 or should_force or force:
                summary = await self._archiver.archive_if_needed(
                    self._agent_id, current_tick, force=(should_force or force)
                )
                logger.info(f"[{self._name}] 归档触发: drama_score={drama_score:.2f}, pending={pending_count}")
                if summary:
                    if self._forgetting_curve:
                        from .forgetting_curve import MemoryEntry
                        entry = MemoryEntry(
                            memory_id=summary.memory_id,
                            agent_id=self._agent_id,
                            content=summary.summary_text,
                            tick_created=current_tick,
                            importance=summary.importance_score,
                            emotion=summary.emotion,
                            is_core=summary.core_memory,
                            context=f"participants: {summary.participants}",
                        )
                        self._forgetting_curve.add_memory(entry)

    async def retrieve_memories(self, query_text: str, current_tick: int) -> str:
        if not self._retriever:
            return ""

        memories = await self._retriever.retrieve(
            agent_id=self._agent_id,
            query_text=query_text,
            current_tick=current_tick,
            neuroticism=self.neuroticism,
        )

        return self._retriever.format_recall_section(memories, self._name)

    def mark_core_memory(self, related_memory_id: str = None) -> None:
        if self._forgetting_curve and related_memory_id:
            self._forgetting_curve.mark_as_core(related_memory_id)

    async def prune_memories(self, current_tick: int) -> None:
        if self._forgetting_curve:
            deleted = self._forgetting_curve.prune_memories(current_tick)
            if deleted:
                logger.info(f"[{self._name}] 删除了 {len(deleted)} 条过期记忆")

    # ==================== V0.7 行为决策 ====================

    async def decide_action(self, tick_type: str, env_state: dict, neighbors: list[str]) -> Optional[dict]:
        if tick_type == "silent":
            return None

        current_tick = getattr(self._world, '_tick_id', 0)
        self._heartbeat_mode.sync_tick(current_tick)

        # V0.7: 心跳模式检查
        if self._heartbeat_mode.should_skip_tick(current_tick):
            if not neighbors:  # 周围确实没人
                idle_action = self._heartbeat_mode.get_idle_action()
                # V0.7: 潜意识动作可能追加到 idle_action
                world_snapshot = {
                    "location": self._current_location or "",
                    "visible_objects": env_state.get("visible_objects", []),
                    "nearby_agents": neighbors,
                    "time_of_day": env_state.get("time_of_day", ""),
                }
                subconscious_result = self._subconscious_engine.match(self, world_snapshot)
                if subconscious_result:
                    idle_action["micro_action"] = subconscious_result["micro_action"]
                logger.debug(f"[{self._name}] 心跳模式: {idle_action['description']}")
                return idle_action

        # 获取记忆上下文
        memory_context = self.get_memory_context()

        # 尝试检索长期记忆
        recall_section = ""
        if self._retriever and tick_type != "silent":
            query = f"当前状态: {env_state.get('time_of_day', 'unknown')}, 附近的人: {', '.join(neighbors) or '无'}"
            recall_section = await self.retrieve_memories(query, current_tick)

        # V0.7: 构建增强版 prompt（整合目标、日程、情绪）
        prompt = self._build_behavior_prompt(env_state, neighbors, memory_context, recall_section)

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个行为决策助手。",
                temperature=0.3,
                max_tokens=150,
            )
            intent = self._parse_intent(response)
            if intent:
                # V0.7: 性格过滤
                filtered = self._personality_filter.filter(intent)
                if filtered is None:
                    logger.info(f"[{self._name}] 意图被性格过滤否决: {intent.get('action_type')}")
                    return {"action_type": "wait", "target": None}
                return filtered
            return None
        except Exception as e:
            logger.warning(f"[{self._name}] 行为决策失败: {e}")
            return None

    def _build_behavior_prompt(
        self,
        env_state: dict,
        neighbors: list[str],
        memory_context: list[dict],
        recall_section: str = "",
    ) -> str:
        loc = self._current_location or "未知"
        time_desc = env_state.get("time_of_day", "unknown")
        weather = env_state.get("weather", "unknown")
        neighbor_desc = ", ".join(neighbors) if neighbors else "无"

        # 短期记忆文本
        memory_text = ""
        if memory_context:
            memory_lines = [f"- {m['role']}: {m['content']}" for m in memory_context[-5:]]
            memory_text = "\n最近记忆:\n" + "\n".join(memory_lines)

        # V0.7: 目标状态
        goal_state = self._goal_manager.get_current_intent()

        # V0.7: 日程状态
        current_activity = self._daily_planner.get_current_activity()
        activity_desc = current_activity.description if current_activity else "例行活动"

        # V0.7: 情绪状态
        emotion_state = self._emotion_model.get_state()

        # V0.7: 情绪行为引导
        emotion_label = emotion_state.get('label', 'neutral')
        if emotion_label == 'anxious':
            emotion_behavior_guide = "你当前感到焦虑，倾向于谨慎行动，避免冒险"
        elif emotion_label == 'happy':
            emotion_behavior_guide = "你心情愉快，更愿意主动社交和尝试新事物"
        elif emotion_label == 'sad':
            emotion_behavior_guide = "你情绪低落，可能更倾向于独处和安静的活动"
        elif emotion_label == 'content':
            emotion_behavior_guide = "你感到满足，倾向于维持现状，保持平稳的行动节奏"
        elif emotion_label == 'curious':
            emotion_behavior_guide = "你充满好奇心，渴望探索新事物"
        else:
            emotion_behavior_guide = "你目前情绪平稳，行动理性"

        # V0.7: 行动风格
        action_style = self._personality_filter.get_action_style()

        # V0.7: 目标截止压力
        goal_deadline_info = ""
        if self._goal_manager.active_goal:
            deadline = self._goal_manager.active_goal.deadline_tick
            if deadline:
                ticks_left = deadline - getattr(self._world, '_tick_id', 0)
                goal_deadline_info = f"\n目标截止: 还有 {ticks_left} Tick"

        return f"""你是 {self._name}，目前在 {loc}。

时间: {time_desc} | 天气: {weather}
附近的人: {neighbor_desc}

{memory_text}
{recall_section}

=== V0.7 角色状态 ===

当前目标: {goal_state.get('active_goal', '无特定目标')}
目标类型: {goal_state.get('goal_type', 'maintenance')}
目标进度: {goal_state.get('goal_progress', 0):.0%}
目标优先级: {goal_state.get('goal_priority', 0):.1f}
{goal_deadline_info}

当前日程: {activity_desc}

情绪状态: {emotion_label} (效价={emotion_state.get('valence', 0):.2f}, 唤醒={emotion_state.get('arousal', 0):.2f})
行为引导: {emotion_behavior_guide}

行动风格: {action_style.get('style_description', '行为稳定')}

请决定下一步行动。输出JSON格式：
{{"action_type": "move|dialogue|wait|observe|idle", "target": "位置名或角色ID或null", "urgency": 0.5, "reasoning": "为什么想这样做"}}

只输出JSON，不要其他内容。"""

    def _parse_intent(self, response: str) -> Optional[dict]:
        import json
        import re
        try:
            match = re.search(r'\{[^}]+\}', response)
            if match:
                parsed = json.loads(match.group())
                # 确保有 action_type 字段
                if 'action_type' in parsed or 'action' in parsed:
                    intent = {
                        "action_type": parsed.get('action_type', parsed.get('action', 'wait')),
                        "target": parsed.get('target'),
                        "urgency": parsed.get('urgency', 0.5),
                        "reasoning": parsed.get('reasoning', ''),
                        "mode": parsed.get('mode', 'reactive'),
                    }
                    return intent
        except json.JSONDecodeError:
            pass
        return None

    # ==================== 运行循环 ====================

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                tick_type = self._world.current_tick_type.value
                env_state = {
                    "time_of_day": self._world._time_of_day.value,
                    "weather": self._world._weather.value,
                }
                neighbors = self._world.neighbors_of(self._agent_id)

                action = await self.decide_action(tick_type, env_state, neighbors)

                if action:
                    action_type = action.get("action_type", "wait")
                    if action_type == "move" and action.get("target"):
                        self._world.move_agent(self._agent_id, action["target"])
                        current_tick = getattr(self._world, '_tick_id', 0)
                        self._heartbeat_mode.on_action_executed(current_tick)
                    elif action_type == "dialogue":
                        pass  # 对话引擎处理

                # 每10 Tick 归档记忆
                current_tick = getattr(self._world, '_tick_id', 0)
                if current_tick > 0 and current_tick % 10 == 0:
                    await self.try_archive(current_tick)

                # 每次 Tick 清理过期记忆
                await self.prune_memories(current_tick)

                # V0.7: 同步游戏时间到日程
                if hasattr(self._world, '_game_hour'):
                    self._daily_planner.sync_hour(self._world._game_hour)
                    # V0.7: 检查是否需要刷新日程（跨天检测）
                    self._daily_planner.refresh_if_needed(
                        game_hour=self._world._game_hour,
                        personality=self._personality,
                        occupation=self._occupation,
                        active_goal=self._goal_manager.active_goal.description if self._goal_manager.active_goal else None,
                        goal_type=self._goal_manager.active_goal.goal_type.value if self._goal_manager.active_goal else None,
                    )

                # V0.7: 检查目标截止压力
                if self._heartbeat_mode.check_goal_deadline_pressure(
                    self._goal_manager.active_goal, current_tick
                ):
                    self._heartbeat_mode.on_action_executed(current_tick)

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self._name}] 运行异常: {e}")

    def start(self) -> None:
        if not self._running:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ==================== V0.7 目标完成回调 ====================

    def _on_goal_share(self, message: str):
        """V0.7: 目标完成分享回调 - 将消息加入对话队列"""
        # 如果角色当前在对话中，可以选择分享目标进展
        logger.info(f"[{self._name}] 目标完成分享: {message}")
        self.add_memory("self", f"我刚刚完成了目标：{message}")

    # ==================== V0.7 外部接口 ====================

    def update_goal_progress(self, goal_id: str, delta: float) -> bool:
        """更新目标进度"""
        return asyncio.create_task(self._goal_manager.update_goal_progress(goal_id, delta))

    def get_emotion_state(self) -> dict:
        """获取当前情绪状态"""
        return self._emotion_model.get_state()

    def trigger_emotion_event(self, event_type: str, event_data: dict = None):
        """触发情绪事件"""
        self._emotion_model.apply_event(event_type, event_data)


class MinimalAgent:
    """简化版 Agent（保持向后兼容）"""
    pass