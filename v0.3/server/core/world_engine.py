"""
world_engine.py — V0.3 世界引擎核心
"""

import asyncio
import logging
import sys
import random
from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict
from enum import Enum
from pathlib import Path

current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from plugins.interfaces import TickType, ISpaceSystem, INarrativeEngine, IScheduler
from plugins.default_plugins import (
    DefaultSpaceSystem, DefaultNarrativeEngine, DefaultScheduler,
    DefaultDesireEngine, DefaultEventBus
)

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


class ActionType(Enum):
    MOVE = "move"
    ENTER = "enter"
    LEAVE = "leave"
    CLOSE_DOOR = "close_door"
    OPEN_DOOR = "open_door"
    LOOK_AROUND = "look_around"
    STAND = "stand"
    SIT = "sit"
    THINK = "think"
    TALK = "talk"
    WAIT = "wait"
    SLEEP = "sleep"
    EAT = "eat"
    DRINK = "drink"
    WALK = "walk"
    RUN = "run"
    HIDE = "hide"
    PREPARE = "prepare"
    OBSERVE = "observe"


@dataclass
class Location:
    id: str
    name: str
    tags: list[str]
    capacity: int = 5


@dataclass
class AgentAction:
    agent_id: str
    agent_name: str
    action_type: ActionType
    description: str
    target_location: Optional[str] = None
    target_agent: Optional[str] = None
    tick: int = 0


@dataclass
class AgentStatus:
    agent_id: str
    location: str
    has_neighbors: bool
    neighbor_ids: list[str]
    active_need: bool
    recent_action: bool


@dataclass
class WorldConfig:
    tick_interval_seconds: float = 1.0
    save_interval_ticks: int = 100
    auto_save_path: str = "data/saves/world_state.json"
    max_agent_memory: int = 20
    silent_tick_ratio: float = 0.7


class WorldEngine:
    """
    V0.3 世界引擎核心
    负责：时间推进、空间管理、环境状态、Tick调度
    """

    def __init__(self, config: Optional[WorldConfig] = None):
        self._config = config or WorldConfig()
        self._tick_id = 0
        self._lock = asyncio.Lock()

        # 子系统
        self._space: ISpaceSystem = DefaultSpaceSystem()
        self._narrative: INarrativeEngine = DefaultNarrativeEngine()
        self._scheduler: IScheduler = DefaultScheduler(self._config.silent_tick_ratio)
        self._desire_engine = DefaultDesireEngine()
        self._event_bus = DefaultEventBus()

        # 数据存储
        self._agents: dict[str, dict] = {}
        self._agent_registry: dict[str, Any] = {}
        self._agent_names: dict[str, str] = {}
        self._locations: dict[str, Location] = {}

        # 环境状态
        self._time_of_day = TimeOfDay.MORNING
        self._weather = Weather.CLEAR
        self._game_hour = 8

        # 感知缓存
        self._perception_cache: dict[str, dict] = {}

        # 当前Tick类型
        self._current_tick_type = TickType.SILENT

        # 对话管理器引用
        self._dialogue_mgr = None

        # 最近对话历史（用于前端展示）
        self._recent_dialogues: list[dict] = []
        self._dialogues_lock = asyncio.Lock()

        # 最近动作历史（用于前端展示）
        self._recent_actions: list[dict] = []

        self._running = False

    def register_location(self, location: Location) -> None:
        self._locations[location.id] = location
        self._space.register_location(location.id, location.name, location.tags, location.capacity)

    def register_agent(self, agent_id: str, name: str, location_id: str) -> None:
        self._agents[agent_id] = {
            "id": agent_id,
            "name": name,
            "location": location_id,
        }
        self._agent_names[agent_id] = name
        self._space.move_agent(agent_id, location_id)
        self._desire_engine.register_agent(agent_id)

    def register_v03_agent(self, agent_id: str, agent: Any) -> None:
        self._agent_registry[agent_id] = agent

    def remove_agent(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        self._agent_names.pop(agent_id, None)
        self._agent_registry.pop(agent_id, None)
        self._space.remove_agent(agent_id)
        return True

    def set_weather(self, weather: str) -> None:
        self._weather = Weather(weather)

    def start_agents(self) -> None:
        for agent_id, agent in self._agent_registry.items():
            if hasattr(agent, 'start') and callable(getattr(agent, 'start')):
                if asyncio.iscoroutinefunction(agent.start):
                    asyncio.create_task(agent.start())
                else:
                    agent.start()

    def get_agent(self, agent_id: str) -> Optional[Any]:
        return self._agent_registry.get(agent_id)

    def neighbors_of(self, agent_id: str) -> list[str]:
        return self._space.get_neighbors(agent_id)

    def current_location(self, agent_id: str) -> Optional[str]:
        return self._space.get_location(agent_id)

    def move_agent(self, agent_id: str, target_location: str) -> bool:
        success = self._space.move_agent(agent_id, target_location)
        if success and agent_id in self._agents:
            self._agents[agent_id]["location"] = target_location
        return success

    async def tick(self) -> dict:
        async with self._lock:
            self._tick_id += 1
            self._advance_time()

            tick_type = self._scheduler.evaluate_tick_type({
                "tick": self._tick_id,
                "has_active_need": self._has_any_active_need(),
                "has_neighbors": self._has_any_neighbors(),
            })
            self._current_tick_type = tick_type

            await self._maybe_move_agents()
            await self._generate_agent_actions()
            await self._check_encounters()

            if self._dialogue_mgr:
                self._dialogue_mgr.broadcast_state()

            result = {
                "tick_id": self._tick_id,
                "time": {
                    "game_hour": self._game_hour,
                    "time_of_day": self._time_of_day.value,
                },
                "weather": self._weather.value,
                "agents": self._serialize_agents(),
                "locations": self._serialize_locations(),
                "tick_type": self._current_tick_type.value,
                "recent_dialogues": self._recent_dialogues[-20:],
                "recent_actions": self._recent_actions[-15:],
            }

            return result

    def _advance_time(self) -> None:
        self._game_hour = (self._game_hour + 1) % 24

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
        elif 22 <= self._game_hour < 24 or self._game_hour == 0:
            self._time_of_day = TimeOfDay.MIDNIGHT
        else:
            self._time_of_day = TimeOfDay.NIGHT

        self._update_weather()

    def _update_weather(self) -> None:
        import random
        if random.random() < 0.05:
            weather_choices = list(Weather)
            self._weather = random.choice(weather_choices)
        self._update_desires_from_environment()

    def _update_desires_from_environment(self) -> None:
        """环境变化影响角色需求"""
        for agent_id in list(self._agents.keys()):
            # 危险天气
            if self._weather in (Weather.STORMY, Weather.RAINY):
                self._desire_engine.update_from_environment(agent_id, "暴风雨天气，安全需求上升")
            # 深夜/午夜
            if self._time_of_day in (TimeOfDay.NIGHT, TimeOfDay.MIDNIGHT):
                self._desire_engine.update_from_environment(agent_id, "深夜独自一人，安全需求上升")

    def _has_any_active_need(self) -> bool:
        for agent_id in self._agents:
            top = self._desire_engine.get_top_need(agent_id)
            if top and top.is_active():
                return True
        return False

    def _has_any_neighbors(self) -> bool:
        for agent_id in self._agents:
            if self._space.get_neighbors(agent_id):
                return True
        return False

    async def _maybe_move_agents(self) -> None:
        import random
        for agent_id in list(self._agents.keys()):
            if self._dialogue_mgr and self._dialogue_mgr.is_agent_active(agent_id):
                continue

            current_loc = self._space.get_location(agent_id)
            if not current_loc:
                continue

            if random.random() < 0.15:
                locations = list(self._locations.keys())
                if len(locations) > 1:
                    new_loc = random.choice(locations)
                    if new_loc != current_loc:
                        self._space.move_agent(agent_id, new_loc)
                        self._agents[agent_id]["location"] = new_loc

    async def _generate_agent_actions(self) -> None:
        for agent_id in list(self._agents.keys()):
            if self._dialogue_mgr and self._dialogue_mgr.is_agent_active(agent_id):
                continue

            action = self._generate_single_agent_action(agent_id)
            if action:
                self._recent_actions.append({
                    "agent_id": action.agent_id,
                    "agent_name": action.agent_name,
                    "action_type": action.action_type.value,
                    "description": action.description,
                    "target_location": action.target_location,
                    "tick": self._tick_id,
                })

                if len(self._recent_actions) > 50:
                    self._recent_actions = self._recent_actions[-50:]

    def _generate_single_agent_action(self, agent_id: str) -> Optional[AgentAction]:
        agent_name = self._agent_names.get(agent_id, agent_id)
        location_id = self._space.get_location(agent_id)
        location = self._locations.get(location_id)

        if not location:
            return None

        action_descriptions = {
            "house": {
                "morning": [
                    f"{agent_name} 从床上醒来",
                    f"{agent_name} 伸了个懒腰",
                    f"{agent_name} 打开窗户透气",
                    f"{agent_name} 洗漱完毕",
                    f"{agent_name} 准备出门",
                ],
                "afternoon": [
                    f"{agent_name} 在房间里休息",
                    f"{agent_name} 整理衣物",
                    f"{agent_name} 阅读书籍",
                    f"{agent_name} 坐在窗边发呆",
                    f"{agent_name} 倒了一杯水",
                ],
                "evening": [
                    f"{agent_name} 回到家中",
                    f"{agent_name} 关上房门",
                    f"{agent_name} 点亮油灯",
                    f"{agent_name} 准备晚餐",
                    f"{agent_name} 坐在炉火旁",
                ],
                "night": [
                    f"{agent_name} 熄灭灯火",
                    f"{agent_name} 准备就寝",
                    f"{agent_name} 躺在床上",
                    f"{agent_name} 轻轻叹息",
                    f"{agent_name} 进入梦乡",
                ],
            },
            "bakery": {
                "morning": [
                    f"{agent_name} 打开店门",
                    f"{agent_name} 开始烘焙面包",
                    f"{agent_name} 摆放货架",
                    f"{agent_name} 擦拭柜台",
                    f"{agent_name} 等待顾客",
                ],
                "afternoon": [
                    f"{agent_name} 整理货架",
                    f"{agent_name} 检查面包新鲜度",
                    f"{agent_name} 招呼客人",
                    f"{agent_name} 包装面包",
                    f"{agent_name} 记录账目",
                ],
                "evening": [
                    f"{agent_name} 清点存货",
                    f"{agent_name} 打扫店铺",
                    f"{agent_name} 关闭店门",
                    f"{agent_name} 上锁",
                    f"{agent_name} 准备回家",
                ],
            },
            "square": {
                "morning": [
                    f"{agent_name} 在广场上散步",
                    f"{agent_name} 四处张望",
                    f"{agent_name} 驻足观察",
                    f"{agent_name} 深呼吸新鲜空气",
                    f"{agent_name} 望着远方",
                ],
                "afternoon": [
                    f"{agent_name} 在广场上徘徊",
                    f"{agent_name} 停下脚步",
                    f"{agent_name} 观察行人",
                    f"{agent_name} 坐在长椅上",
                    f"{agent_name} 陷入沉思",
                ],
                "evening": [
                    f"{agent_name} 在广场上漫步",
                    f"{agent_name} 欣赏夕阳",
                    f"{agent_name} 准备回家",
                    f"{agent_name} 加快脚步",
                    f"{agent_name} 回头望了望",
                ],
            },
        }

        weather_actions = {
            Weather.RAINY: [
                f"{agent_name} 撑起雨伞",
                f"{agent_name} 快步前行",
                f"{agent_name} 寻找避雨处",
                f"{agent_name} 抖落身上的雨水",
                f"{agent_name} 抱怨天气",
            ],
            Weather.STORMY: [
                f"{agent_name} 急忙寻找遮蔽",
                f"{agent_name} 关上窗户",
                f"{agent_name} 拉紧衣领",
                f"{agent_name} 担心天气",
                f"{agent_name} 自言自语",
            ],
            Weather.SNOWY: [
                f"{agent_name} 裹紧大衣",
                f"{agent_name} 在雪地上留下脚印",
                f"{agent_name} 搓着手取暖",
                f"{agent_name} 看着飘落的雪花",
                f"{agent_name} 哈着热气",
            ],
            Weather.FOGGY: [
                f"{agent_name} 小心前行",
                f"{agent_name} 四处张望",
                f"{agent_name} 放慢脚步",
                f"{agent_name} 感到神秘",
                f"{agent_name} 轻声呼唤",
            ],
        }

        location_tags = location.tags if location else []
        location_category = "house"
        
        if location_id:
            if "bakery" in location_id.lower():
                location_category = "bakery"
            elif "square" in location_id.lower():
                location_category = "square"
            elif "house" in location_id.lower():
                location_category = "house"
            elif "tavern" in location_id.lower():
                location_category = "house"
        
        if not location_category:
            if "commercial" in location_tags:
                location_category = "bakery"
            elif "public" in location_tags:
                location_category = "square"
            elif "private" in location_tags:
                location_category = "house"

        time_category = "afternoon"
        if self._time_of_day in (TimeOfDay.DAWN, TimeOfDay.MORNING):
            time_category = "morning"
        elif self._time_of_day in (TimeOfDay.EVENING, TimeOfDay.NIGHT, TimeOfDay.MIDNIGHT):
            time_category = "night" if self._time_of_day in (TimeOfDay.NIGHT, TimeOfDay.MIDNIGHT) else "evening"

        possible_actions = []

        if location_category in action_descriptions and time_category in action_descriptions[location_category]:
            possible_actions.extend(action_descriptions[location_category][time_category])

        if self._weather in weather_actions:
            possible_actions.extend(weather_actions[self._weather])

        if not possible_actions:
            possible_actions = [
                f"{agent_name} 四处张望",
                f"{agent_name} 站立不动",
                f"{agent_name} 若有所思",
                f"{agent_name} 等待着什么",
            ]

        if random.random() < 0.1:
            return None

        selected_desc = random.choice(possible_actions)
        action_type = self._determine_action_type(selected_desc)

        return AgentAction(
            agent_id=agent_id,
            agent_name=agent_name,
            action_type=action_type,
            description=selected_desc,
            target_location=location_id,
            tick=self._tick_id,
        )

    def _determine_action_type(self, description: str) -> ActionType:
        if "离开" in description or "出门" in description or "回家" in description:
            return ActionType.LEAVE
        elif "进入" in description or "打开" in description or "进入" in description:
            return ActionType.ENTER
        elif "关" in description or "锁" in description:
            return ActionType.CLOSE_DOOR
        elif "打开" in description:
            return ActionType.OPEN_DOOR
        elif "走" in description or "漫步" in description or "前行" in description:
            return ActionType.WALK
        elif "跑" in description:
            return ActionType.RUN
        elif "坐" in description:
            return ActionType.SIT
        elif "站" in description:
            return ActionType.STAND
        elif "看" in description or "望" in description:
            return ActionType.OBSERVE
        elif "想" in description:
            return ActionType.THINK
        elif "等待" in description:
            return ActionType.WAIT
        elif "睡" in description:
            return ActionType.SLEEP
        else:
            return ActionType.STAND

    async def _check_encounters(self) -> None:
        processed_pairs = set()
        for agent_id in list(self._agents.keys()):
            neighbors = self._space.get_neighbors(agent_id)
            for neighbor_id in neighbors:
                pair_key = tuple(sorted([agent_id, neighbor_id]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                if self._dialogue_mgr:
                    if not self._dialogue_mgr.is_agent_active(agent_id) and \
                       not self._dialogue_mgr.is_agent_active(neighbor_id):
                        asyncio.create_task(
                            self._dialogue_mgr.trigger_dialogue(agent_id, neighbor_id, self._agent_registry)
                        )

    def _serialize_agents(self) -> list[dict]:
        result = []
        moods = ["开心", "平静", "疲惫", "焦虑", "好奇", "专注", "放松", "期待"]
        intentions = ["休息", "工作", "社交", "探索", "思考", "观察", "等待"]
        
        for agent_id, info in self._agents.items():
            loc = info.get("location", "未知")
            neighbors = self._space.get_neighbors(agent_id)
            agent = self._agent_registry.get(agent_id)
            
            # 获取人格信息
            personality = None
            if agent and hasattr(agent, '_personality'):
                p = agent._personality
                personality = {
                    "openness": round(p.get("openness", 0.5), 2),
                    "conscientiousness": round(p.get("conscientiousness", 0.5), 2),
                    "extraversion": round(p.get("extraversion", 0.5), 2),
                    "agreeableness": round(p.get("agreeableness", 0.5), 2),
                    "neuroticism": round(p.get("neuroticism", 0.3), 2),
                }
            
            # 获取需求信息（从 desire_engine）
            desires = self._desire_engine.get_desires(agent_id) if hasattr(self._desire_engine, 'get_desires') else None
            
            # 随机生成情绪和意图（可以根据时间、天气、位置调整）
            import random
            mood = random.choice(moods)
            intention = random.choice(intentions)
            
            # 根据时间调整情绪
            if self._time_of_day in (TimeOfDay.NIGHT, TimeOfDay.MIDNIGHT):
                if random.random() > 0.5:
                    mood = "疲惫"
                    intention = "休息"
            elif self._time_of_day == TimeOfDay.MORNING:
                if random.random() > 0.5:
                    mood = "期待"
                    intention = "工作"
            
            result.append({
                "id": agent_id,
                "name": info["name"],
                "location": loc,
                "neighbors": neighbors,
                "is_active": self._dialogue_mgr.is_agent_active(agent_id) if self._dialogue_mgr else False,
                "personality": personality,
                "mood": mood,
                "intention": intention,
                "desires": desires,
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
                "agents": agents_here,
            })
        return result

    async def save(self, path: str) -> None:
        import json
        data = {
            "tick_id": self._tick_id,
            "game_hour": self._game_hour,
            "weather": self._weather.value,
            "agents": self._agents,
            "locations": {
                lid: {"id": loc.id, "name": loc.name, "tags": loc.tags, "capacity": loc.capacity}
                for lid, loc in self._locations.items()
            },
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def load(self, path: str) -> None:
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._tick_id = data.get("tick_id", 0)
        self._game_hour = data.get("game_hour", 8)
        self._agents = data.get("agents", {})

    def set_dialogue_manager(self, dm) -> None:
        self._dialogue_mgr = dm

    @property
    def config(self) -> WorldConfig:
        return self._config

    @property
    def current_tick_type(self) -> TickType:
        return self._current_tick_type

    @property
    def agent_names(self) -> dict[str, str]:
        return self._agent_names

    async def add_dialogue(self, dialogue: dict) -> None:
        """记录一条对话到世界状态，供前端展示"""
        async with self._dialogues_lock:
            self._recent_dialogues.append(dialogue)
            if len(self._recent_dialogues) > 50:
                self._recent_dialogues = self._recent_dialogues[-50:]

    async def reset_world(self, world_data: dict, characters: list[dict], llm=None) -> None:
        """重置世界，加载新生成的世界和角色数据"""
        async with self._lock:
            # 清空现有数据
            self._agents.clear()
            self._agent_registry.clear()
            self._agent_names.clear()
            self._locations.clear()
            self._recent_dialogues.clear()
            self._recent_actions.clear()

            # 重置时间和状态
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

            # 加载新角色（同时创建 MinimalAgent）
            from core.agent import MinimalAgent
            for char_data in characters:
                agent_id = char_data["id"]
                name = char_data["name"]
                location_id = char_data.get("initial_location", "")
                if location_id and location_id not in self._locations:
                    location_id = list(self._locations.keys())[0] if self._locations else ""
                if location_id:
                    self.register_agent(agent_id, name, location_id)
                    # 创建完整的 MinimalAgent
                    agent = MinimalAgent(
                        agent_id=agent_id,
                        name=name,
                        llm=llm if llm is not None else getattr(self, '_llm', None),
                        world=self,
                        initial_location=location_id,
                    )
                    # 设置角色详细信息
                    if char_data.get("personality"):
                        p = char_data["personality"]
                        agent.personality = {
                            "openness": p.get("openness", 0.5),
                            "conscientiousness": p.get("conscientiousness", 0.5),
                            "extraversion": p.get("extraversion", 0.5),
                            "agreeableness": p.get("agreeableness", 0.5),
                            "neuroticism": p.get("neuroticism", 0.5),
                        }
                    if char_data.get("identity_tags"):
                        agent.identity_tags = char_data["identity_tags"]
                    if char_data.get("mood"):
                        agent.mood = char_data["mood"]
                    if char_data.get("intention"):
                        agent.intention = char_data["intention"]
                    if char_data.get("backstory"):
                        agent.backstory = char_data["backstory"]
                    self.register_v03_agent(agent_id, agent)

            logger.info(f"[WorldEngine] 世界已重置: {len(self._locations)} 地点, {len(self._agents)} 角色")
