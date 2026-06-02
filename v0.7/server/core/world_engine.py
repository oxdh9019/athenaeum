"""
world_engine.py — V0.5 世界引擎
V0.3 基础 + V0.5 记忆系统集成
"""

import asyncio
import logging
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)


class TimeOfDay(Enum):
    DAWN = "dawn"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    MIDNIGHT = "midnight"


class Weather(Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    SNOWY = "snowy"
    FOGGY = "foggy"


class TickType(Enum):
    SILENT = "silent"
    ACTIVE = "active"


@dataclass
class Location:
    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    capacity: int = 10


@dataclass
class WorldConfig:
    tick_interval_seconds: float = 2.0
    save_interval_ticks: int = 100
    silent_tick_ratio: float = 0.7


class DefaultScheduler:
    """调度器：决定每个 Tick 是 SILENT 还是 ACTIVE"""

    def __init__(self, silent_ratio: float = 0.7):
        self._silent_ratio = silent_ratio
        self._tick_count = 0

    def evaluate_tick_type(self, env_state: dict) -> str:
        self._tick_count += 1
        # 静默tick跳过LLM调用，降低成本
        if self._tick_count % 10 < (10 * self._silent_ratio):
            return TickType.SILENT.value
        return TickType.ACTIVE.value


class DefaultSpaceSystem:
    """空间系统：管理地点和角色位置"""

    def __init__(self):
        self._locations: dict[str, Location] = {}
        self._agent_locations: dict[str, str] = {}  # agent_id -> location_id

    def register_location(self, location: Location):
        self._locations[location.id] = location

    def register_agent(self, agent_id: str, location_id: str):
        self._agent_locations[agent_id] = location_id

    def move_agent(self, agent_id: str, target_location: str) -> bool:
        if target_location not in self._locations:
            return False
        self._agent_locations[agent_id] = target_location
        return True

    def current_location(self, agent_id: str) -> Optional[str]:
        return self._agent_locations.get(agent_id)

    def neighbors_of(self, agent_id: str) -> list[str]:
        current = self.current_location(agent_id)
        if not current:
            return []
        current_loc = self._locations.get(current)
        if not current_loc:
            return []
        # 同一地点的其他 agent
        return [
            aid for aid, loc_id in self._agent_locations.items()
            if loc_id == current and aid != agent_id
        ]

    def get_location(self, location_id: str) -> Optional[Location]:
        return self._locations.get(location_id)

    def get_all_locations(self) -> dict[str, Location]:
        return self._locations.copy()


class WorldEngine:
    """
    V0.5 世界引擎
    V0.3 基础 + 记忆系统集成
    V0.6 叙事引擎集成
    """

    def __init__(self, config: WorldConfig = None):
        self.config = config or WorldConfig()

        self._tick_id = 0
        self._game_hour = 8  # 游戏内小时
        self._time_of_day = TimeOfDay.MORNING
        self._weather = Weather.CLEAR

        self._locations: dict[str, Location] = {}
        self._agents: dict[str, dict] = {}  # agent_id -> metadata
        self._agent_registry: dict[str, Any] = {}  # agent_id -> Agent实例

        self._scheduler = DefaultScheduler(self.config.silent_tick_ratio)
        self._space = DefaultSpaceSystem()

        self._dialogue_mgr = None

        self._recent_dialogues: list[dict] = []
        # deque(maxlen) 自动截断，避免长跑世界无限增长
        self._recent_actions: deque[dict] = deque(maxlen=200)

        self._lock = asyncio.Lock()
        self._current_tick_type = TickType.SILENT

        # V0.6 叙事引擎组件
        self._collective_mood = None
        self._opportunity_detector = None
        self._narrative_injector = None
        self._world_will = None
        self._archiver = None
        self._timeline_service = None
        self._ws_broadcast_fn = None

        # V0.7 世界隔离 ID
        self._world_session_id = "default"

        # 持有对话 task 引用，防止 asyncio.create_task 的弱引用被 GC 回收
        self._dialogue_tasks: set = set()
        # V0.7 Phase C2.5: WS 广播 task 同样持强引用 + done callback 清理
        # 否则 _broadcast_ws 的 create_task 可能被 GC, 广播丢失
        self._ws_tasks: set = set()

    @property
    def agent_names(self) -> dict[str, str]:
        return {aid: info["name"] for aid, info in self._agents.items()}

    def set_dialogue_manager(self, dm):
        self._dialogue_mgr = dm

    @property
    def current_tick_type(self):
        return self._current_tick_type

    # ==================== 位置管理 ====================

    def register_location(self, location: Location):
        self._locations[location.id] = location
        self._space.register_location(location)

    # ==================== Agent 管理 ====================

    def register_agent(self, agent_id: str, name: str, location_id: str = None):
        self._agents[agent_id] = {
            "id": agent_id,
            "name": name,
            "location": location_id,
        }
        if location_id:
            self._space.register_agent(agent_id, location_id)

    def register_v05_agent(self, agent_id: str, agent):
        """注册 V0.5 Agent（含记忆系统）"""
        self._agent_registry[agent_id] = agent

    def register_v07_agent(self, agent_id: str, agent):
        """注册 V0.7 Agent（拟人化版本：含 soul、目标、潜意识）"""
        self._agent_registry[agent_id] = agent

    def register_v03_agent(self, agent_id: str, agent):
        """注册 V0.3 Agent（兼容）"""
        self._agent_registry[agent_id] = agent

    # ==================== V0.6 叙事引擎组件注册 ====================

    def set_collective_mood(self, mood):
        """设置集体情绪组件"""
        self._collective_mood = mood

    def set_opportunity_detector(self, detector):
        """设置机会检测器"""
        self._opportunity_detector = detector

    def set_narrative_injector(self, injector):
        """设置叙事注入器"""
        self._narrative_injector = injector

    def set_world_will(self, will):
        """设置世界意志配置"""
        self._world_will = will

    def set_archiver(self, archiver):
        """设置记忆归档器"""
        self._archiver = archiver

    def set_timeline_service(self, timeline):
        """设置时间线服务"""
        self._timeline_service = timeline

    def set_ws_broadcast(self, fn):
        """设置 WebSocket 广播函数"""
        self._ws_broadcast_fn = fn

    # ==================== 公开 API（供 OpportunityDetector 使用） ====================

    def get_all_locations(self):
        """获取所有地点"""
        return list(self._locations.values())

    def get_agents_at_location(self, location_id: str) -> list:
        """获取指定地点的所有角色 ID"""
        return [
            aid for aid, loc in self._space._agent_locations.items()
            if loc == location_id
        ]

    def get_agent(self, agent_id: str):
        """获取角色实例"""
        return self._agent_registry.get(agent_id)

    def get_relationship(self, agent_a: str, agent_b: str):
        """获取两个角色间的关系值（供 OpportunityDetector 使用）"""
        agent = self._agent_registry.get(agent_a)
        if not agent:
            return None
        if hasattr(agent, '_relationships'):
            return agent._relationships.get(agent_b, 0.5)
        if hasattr(agent, 'relationships'):
            return getattr(agent.relationships, agent_b, 0.5)
        return 0.5  # 默认中等关系

    def get_all_agents(self) -> list:
        """获取所有角色实例"""
        return list(self._agent_registry.values())

    def _broadcast_ws(self, payload: dict):
        """内部广播方法（供 NarrativeInjector 调用）"""
        if self._ws_broadcast_fn:
            try:
                # V0.7 Phase C2.5: 持强引用 + done callback 清理
                # 之前直接 asyncio.create_task 不持引用, 可能在 event loop
                # 调度前被 GC, 造成广播丢失
                import asyncio
                task = asyncio.create_task(self._ws_broadcast_fn(payload))
                self._ws_tasks.add(task)
                task.add_done_callback(self._ws_tasks.discard)
            except Exception:
                pass

    def record_timeline_event(self, event_type: str, description: str, participants: list, tick: int = None):
        """记录时间线事件（供叙事注入器调用）"""
        if self._timeline_service:
            self._timeline_service.record_event(event_type, description, participants, tick)

    def move_agent(self, agent_id: str, target_location: str) -> bool:
        success = self._space.move_agent(agent_id, target_location)
        if success:
            if agent_id in self._agents:
                self._agents[agent_id]["location"] = target_location
            action = f"{self._agents.get(agent_id, {}).get('name', agent_id)} 前往 {target_location}"
            self._recent_actions.append({"tick": self._tick_id, "action": action})
        return success

    def neighbors_of(self, agent_id: str) -> list[str]:
        return self._space.neighbors_of(agent_id)

    # ==================== 时间系统 ====================

    def _advance_time(self):
        self._tick_id += 1
        self._game_hour = (self._game_hour + 1) % 24

        # 时间段
        if 5 <= self._game_hour < 8:
            self._time_of_day = TimeOfDay.DAWN
        elif 8 <= self._game_hour < 12:
            self._time_of_day = TimeOfDay.MORNING
        elif 12 <= self._game_hour < 14:
            self._time_of_day = TimeOfDay.NOON
        elif 14 <= self._game_hour < 18:
            self._time_of_day = TimeOfDay.AFTERNOON
        elif 18 <= self._game_hour < 22:
            self._time_of_day = TimeOfDay.EVENING
        elif 22 <= self._game_hour < 24 or 0 <= self._game_hour < 5:
            self._time_of_day = TimeOfDay.NIGHT if self._game_hour >= 22 else TimeOfDay.MIDNIGHT

    def _update_weather(self):
        """随机天气变化（5%概率）"""
        import random
        if random.random() < 0.05:
            weathers = list(Weather)
            self._weather = random.choice(weathers)

    # ==================== Tick 循环 ====================

    async def tick(self) -> dict:
        async with self._lock:
            self._tick_id += 1
            self._advance_time()
            self._update_weather()

            # 评估 tick 类型
            tick_type = self._scheduler.evaluate_tick_type({
                "time_of_day": self._time_of_day.value,
                "weather": self._weather.value,
            })
            self._current_tick_type = TickType(tick_type)

            # V0.6 叙事引擎：集体情绪评估
            if self._collective_mood:
                agents = self.get_all_agents()
                self._collective_mood.evaluate(agents)

            # V0.6 叙事引擎：机会扫描
            signals = []
            if self._opportunity_detector and self._current_tick_type == TickType.ACTIVE:
                signals = self._opportunity_detector.scan()

            # V0.6 叙事引擎：生成并分发叙事事件
            if signals and self._narrative_injector:
                world_will = self._world_will
                for sig in signals:
                    event = await self._narrative_injector.generate_event_from_signal(sig, world_will)
                    if event:
                        await self._narrative_injector.dispatch_event(event)
                        self.record_timeline_event(
                            event.event_type.value,
                            event.description,
                            event.affected_agents,
                            event.tick
                        )
                        await self._narrative_injector.broadcast_drama_event(event)

            # V0.6 记忆归档
            if self._archiver:
                await self._archiver.increment_tick()

            # 移动
            await self._maybe_move_agents()

            # 生成动作
            await self._generate_agent_actions()

            # 检查相遇
            await self._check_encounters()

            if self._dialogue_mgr:
                self._dialogue_mgr.broadcast_state()

            return self._get_state()

    async def _maybe_move_agents(self):
        """15%概率随机移动"""
        import random
        for agent_id in list(self._agents.keys()):
            if self._agent_registry.get(agent_id):
                if random.random() < 0.15:
                    current_loc = self._space.current_location(agent_id)
                    if current_loc:
                        # 随机移动到相邻地点（简化：随机选择）
                        same_loc_agents = [
                            aid for aid, loc in self._space._agent_locations.items()
                            if loc == current_loc
                        ]
                        if len(same_loc_agents) > 1:
                            # 有其他人在同一地点，可能触发对话
                            pass

    async def _generate_agent_actions(self):
        """生成 Agent 动作描述"""
        import random
        active_agents = [
            aid for aid in self._agents.keys()
            if self._agent_registry.get(aid) and self._current_tick_type == TickType.ACTIVE
        ]

        for agent_id in active_agents:
            agent = self._agent_registry.get(agent_id)
            if not agent:
                continue

            location = self._space.current_location(agent_id)
            neighbors = self._space.neighbors_of(agent_id)

            if not neighbors:
                # 没有邻居，执行等待动作
                action_desc = self._get_idle_action_description()
                action_type = "idle"
            else:
                # 有邻居，正在对话或互动
                action_desc = "与周围角色交流中"
                action_type = "interact"

            self._recent_actions.append({
                "tick": self._tick_id,
                "agent_id": agent_id,
                "agent_name": self._agents.get(agent_id, {}).get("name", agent_id),
                "action_type": action_type,
                "description": action_desc,
                "target_location": location,
            })

    def _get_idle_action_description(self) -> str:
        """根据时间和天气生成等待动作描述"""
        time_descriptions = {
            TimeOfDay.DAWN: "迎着晨曦",
            TimeOfDay.MORNING: "在晨光中",
            TimeOfDay.NOON: "在阳光下",
            TimeOfDay.AFTERNOON: "在午后",
            TimeOfDay.EVENING: "在暮色中",
            TimeOfDay.NIGHT: "在夜色中",
            TimeOfDay.MIDNIGHT: "在深夜",
        }

        weather_descriptions = {
            Weather.CLEAR: "静静地思考",
            Weather.CLOUDY: "望着天空",
            Weather.RAINY: "听着雨声",
            Weather.STORMY: "躲避风雨",
            Weather.SNOWY: "看着雪花",
            Weather.FOGGY: "在雾中",
        }

        time_desc = time_descriptions.get(self._time_of_day, "")
        weather_desc = weather_descriptions.get(self._weather, "")

        return f"{time_desc}{weather_desc}"

    async def _check_encounters(self):
        """检查相遇并触发对话"""
        if not self._dialogue_mgr:
            return

        processed_pairs = set()
        triggered = 0

        for agent_id in list(self._agents.keys()):
            neighbors = self._space.neighbors_of(agent_id)
            for neighbor_id in neighbors:
                pair_key = tuple(sorted([agent_id, neighbor_id]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                # 检查是否已经在对话中
                if not self._dialogue_mgr.is_agent_active(agent_id) and \
                   not self._dialogue_mgr.is_agent_active(neighbor_id):
                    task = asyncio.create_task(
                        self._dialogue_mgr.trigger_dialogue(agent_id, neighbor_id, self._agent_registry)
                    )
                    self._dialogue_tasks.add(task)
                    task.add_done_callback(self._dialogue_tasks.discard)
                    triggered += 1
                    logger.debug(f"[encounter] tick={self._tick_id} trigger dialogue {agent_id}<->{neighbor_id}")

        if triggered:
            logger.debug(f"[encounter] tick={self._tick_id} triggered {triggered} dialogue(s)")

    # ==================== 对话记录 ====================

    async def add_dialogue(self, dialogue_data: dict):
        """添加对话到历史记录"""
        self._recent_dialogues.append(dialogue_data)
        # 保持最近50条
        if len(self._recent_dialogues) > 50:
            self._recent_dialogues.pop(0)
        # V0.6: 同时记录到时间线
        if self._timeline_service:
            self._timeline_service.record_event(
                event_type="dialogue",
                description=f"{dialogue_data.get('from', '')}: {dialogue_data.get('utterance', '')[:80]}",
                participants=[dialogue_data.get('from', ''), dialogue_data.get('to', '')],
                tick=dialogue_data.get('tick', self._tick_id),
            )

    # ==================== 世界重置 ====================

    async def reset_world(
        self,
        world_data: dict,
        characters: list[dict],
        llm=None,
        cloud_llm=None,
        local_llm=None,
        archiver=None,
        retriever=None,
        forgetting_curves: dict = None,
    ) -> None:
        """
        重置世界,加载新生成的世界和角色数据(使用 V07Agent)。
        """
        from utils.ids import short_id
        async with self._lock:
            # V0.7: 生成新的世界会话 ID,实现数据隔离(48-bit 熵)
            self._world_session_id = short_id()

            self._agents.clear()
            self._agent_registry.clear()
            self._agent_names.clear() if hasattr(self, '_agent_names') else None
            self._locations.clear()
            self._recent_dialogues.clear()
            self._recent_actions.clear()

            self._tick_id = 0
            self._time_of_day = TimeOfDay.MORNING
            self._game_hour = 8

            # 加载新地点
            for loc_data in world_data.get("locations", []):
                location = Location(
                    id=loc_data["id"],
                    name=loc_data["name"],
                    tags=loc_data.get("tags", []),
                    capacity=loc_data.get("capacity", 5),
                )
                self.register_location(location)

            # 加载新角色(V07Agent)
            from core.v07_agent import V07Agent
            from core.heartbeat_mode import HeartbeatConfig

            heartbeat_min = forgetting_curves.pop("_heartbeat_min", 4) if forgetting_curves else 4
            heartbeat_max = forgetting_curves.pop("_heartbeat_max", 8) if forgetting_curves else 8

            for char_data in characters:
                agent_id = char_data["id"]
                name = char_data["name"]
                location_id = char_data.get("initial_location", "")
                if location_id and location_id not in self._locations:
                    location_id = list(self._locations.keys())[0] if self._locations else ""
                personality = char_data.get("personality") or {
                    "openness": 0.6, "conscientiousness": 0.5, "extraversion": 0.5,
                    "agreeableness": 0.5, "neuroticism": 0.4,
                }
                soul = char_data.get("soul") or {}
                occupation = char_data.get("occupation") or (
                    char_data.get("identity_tags", {}).get("primary", "") if isinstance(char_data.get("identity_tags"), dict) else ""
                )
                forgetting_curve = (forgetting_curves or {}).get(agent_id)

                # heartbeat 用全局 env 配置
                hb_config = HeartbeatConfig(
                    enabled=True,
                    min_interval=heartbeat_min,
                    max_interval=heartbeat_max,
                    base_interval=max(heartbeat_min, min(heartbeat_max, 6)),
                )

                if location_id:
                    self.register_agent(agent_id, name, location_id)
                    agent = V07Agent(
                        agent_id=agent_id,
                        name=name,
                        personality=personality,
                        occupation=occupation,
                        soul=soul,
                        llm=llm or local_llm or cloud_llm,
                        world=self,
                        initial_location=location_id,
                        cloud_llm=cloud_llm,
                        local_llm=local_llm,
                        archiver=archiver,
                        retriever=retriever,
                        forgetting_curve=forgetting_curve,
                    )
                    # 异步初始化(从 soul 生成目标)
                    try:
                        await agent.initialize()
                    except Exception as e:
                        logger.warning(f"[WorldEngine] agent {name}.initialize() 失败: {e}")
                    self.register_v07_agent(agent_id, agent)
                else:
                    logger.warning(f"[WorldEngine] 角色 {name} 没有合法 location,跳过")

            logger.info(f"[WorldEngine] 世界已重置: {len(self._locations)} 地点, {len(self._agents)} 角色 (V07Agent)")

    # ==================== 状态序列化 ====================

    def _serialize_agents(self) -> list[dict]:
        result = []
        for agent_id, info in self._agents.items():
            agent = self._agent_registry.get(agent_id)
            location = self._space.current_location(agent_id)
            neighbors = self._space.neighbors_of(agent_id)
            # 检查是否在对话中
            is_active = False
            if hasattr(self, '_dialogue_mgr') and self._dialogue_mgr:
                is_active = self._dialogue_mgr.is_agent_active(agent_id)

            # V0.7: 从 V07Agent 读富字段
            emotion_state = None
            active_goal = None
            current_action = None
            last_decision = None
            if agent is not None and hasattr(agent, 'get_emotion_state'):
                try:
                    emotion_state = agent.get_emotion_state()
                except Exception:
                    pass
            if agent is not None and hasattr(agent, '_goal_manager'):
                try:
                    g = agent._goal_manager.active_goal
                    if g is not None:
                        active_goal = {
                            "id": g.id if hasattr(g, 'id') else None,
                            "type": g.goal_type.value if hasattr(g, 'goal_type') and g.goal_type else None,
                            "description": g.description if hasattr(g, 'description') else str(g),
                            "progress": getattr(g, 'progress', 0.0) if hasattr(g, 'progress') else 0.0,
                        }
                except Exception:
                    pass
            if agent is not None and hasattr(agent, '_state') and isinstance(agent._state, dict):
                current_action = agent._state.get("current_action")
                last_decision = agent._state.get("last_decision")

            # mood: 字符串或 None; backend 留 None 而不是 "" 让前端用 ?. 兜底
            raw_mood = getattr(agent, 'mood', None) if agent is not None else None
            result.append({
                "id": agent_id,
                "name": info["name"],
                "location": location,
                "neighbors": neighbors,
                "is_active": is_active,
                "mood": raw_mood if isinstance(raw_mood, str) else None,
                "personality": getattr(agent, 'personality', None) if agent is not None else None,
                "emotion_state": emotion_state,
                "active_goal": active_goal,
                "current_action": current_action,
                "last_decision": last_decision,
            })
        return result

    def _serialize_locations(self) -> list[dict]:
        result = []
        for loc_id, loc in self._locations.items():
            agents_here = [
                aid for aid, info in self._agents.items()
                if info.get("location") == loc_id
            ]
            result.append({
                "id": loc_id,
                "name": loc.name,
                "tags": loc.tags,
                "capacity": loc.capacity,
                "agents": agents_here,
            })
        return result

    def _get_state(self) -> dict:
        return {
            "tick_id": self._tick_id,
            "time": {
                "game_hour": self._game_hour,
                "time_of_day": self._time_of_day.value,
            },
            "weather": self._weather.value,
            "tick_type": self._current_tick_type.value,
            "agents": self._serialize_agents(),
            "locations": self._serialize_locations(),
            "recent_dialogues": self._recent_dialogues[-20:],
            "recent_actions": list(self._recent_actions)[-15:],
        }