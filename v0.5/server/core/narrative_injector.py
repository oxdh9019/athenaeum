"""
narrative_injector.py — V0.6 叙事注入器升级版
集成机会检测信号、世界意志配置、事件分发
"""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class SystemEventType(Enum):
    STRANGER_ARRIVES = "stranger_arrives"
    NEWS_SPREADS = "news_spreads"
    WEATHER_CHANGE = "weather_change"
    RUMOR = "rumor"
    OPPORTUNITY = "opportunity"
    CONFLICT = "conflict"
    ROMANCE = "romance"
    COOPERATION = "cooperation"
    DRAMA_EVENT = "drama_event"  # V0.6 新增：叙事事件


@dataclass
class SystemEvent:
    event_id: str
    event_type: SystemEventType
    description: str
    affected_agents: list[str]
    tick: int


class NarrativeInjector:
    """
    叙事注入器 — V0.6 升级版

    职责:
    - 评估 drama_tension（统计最近10个Tick的对话次数、关系变化幅度）
    - 若 tension < 阈值，生成系统事件并广播
    - 接收 opportunity_detector 的信号，生成叙事事件
    - 根据 world_will 调整事件生成风格
    - 事件分发给涉及角色 + 记录到 Timeline
    """

    def __init__(
        self,
        world,
        cloud_llm,
        tension_threshold: float = 0.3,
        window_ticks: int = 10,
        world_will=None,
    ):
        self._world = world
        self._cloud = cloud_llm
        self._tension_threshold = tension_threshold
        self._window_ticks = window_ticks
        self._tick_events: list[dict] = []  # 每Tick的统计数据
        self._pending_events: list[SystemEvent] = []
        self._event_counter = 0
        self._world_will = world_will  # WorldWill 配置

    def set_world_will(self, world_will) -> None:
        """设置世界意志配置"""
        self._world_will = world_will

    def record_dialogue(self, agent_a: str, agent_b: str, relationship_delta: float):
        """记录一次对话交互"""
        self._tick_events.append({
            "type": "dialogue",
            "agents": (agent_a, agent_b),
            "rel_delta": relationship_delta,
            "tick": len(self._tick_events),
        })
        self._prune_window()

    def record_interaction(self, agent_a: str, agent_b: str, interaction_type: str):
        """记录一次互动（不只是对话）"""
        self._tick_events.append({
            "type": interaction_type,
            "agents": (agent_a, agent_b),
            "rel_delta": 0.0,
            "tick": len(self._tick_events),
        })
        self._prune_window()

    def _prune_window(self):
        """保持最近 window_ticks 条记录"""
        if len(self._tick_events) > self._window_ticks:
            self._tick_events = self._tick_events[-self._window_ticks:]

    def compute_tension(self) -> float:
        """
        计算 drama_tension ∈ [0, 1]

        计算方式:
        - 对话频率：窗口内对话次数 / 窗口大小
        - 关系变化幅度：平均 |delta|
        """
        if not self._tick_events:
            return 0.0

        window = self._tick_events[-self._window_ticks:]
        dialogue_count = sum(1 for e in window if e["type"] == "dialogue")
        rel_changes = [abs(e["rel_delta"]) for e in window if e["rel_delta"] != 0]
        avg_rel_change = sum(rel_changes) / len(rel_changes) if rel_changes else 0.0

        dialogue_factor = min(dialogue_count / self._window_ticks, 1.0)
        change_factor = min(avg_rel_change * 2, 1.0)

        tension = dialogue_factor * 0.6 + change_factor * 0.4
        logger.debug(f"[叙事注入] tension={tension:.3f} (对话:{dialogue_factor:.2f} 变化:{change_factor:.2f})")
        return tension

    def should_inject(self) -> bool:
        """判断是否需要注入事件"""
        return self.compute_tension() < self._tension_threshold

    async def generate_event_from_signal(self, signal, world_will) -> Optional[SystemEvent]:
        """
        根据 opportunity_detector 的信号生成叙事事件
        V0.6 核心功能
        """
        self._event_counter += 1
        event_id = f"narrative_{self._event_counter}"

        signal_type = signal.signal_type if hasattr(signal, 'signal_type') else signal.get('type', 'unknown')
        participants = signal.participants if hasattr(signal, 'participants') else signal.get('agents', [])

        # 根据信号类型和 world_will 生成事件描述
        try:
            location_names = []
            if hasattr(self._world, 'get_all_locations'):
                try:
                    locations = self._world.get_all_locations()
                    location_names = [loc.name if hasattr(loc, 'name') else str(loc) for loc in locations]
                except Exception:
                    pass

            agent_names = []
            for pid in participants:
                agent = self._world.get_agent(pid) if hasattr(self._world, 'get_agent') else None
                if agent:
                    agent_names.append(getattr(agent, '_name', pid))
                else:
                    agent_names.append(pid)

            # 构建 world_will 上下文
            will_context = ""
            if world_will:
                will_context = f"世界意志配置: 冲突频率={world_will.conflict_frequency}, 合作鼓励={world_will.cooperation_encouragement}, 浪漫偏好={world_will.romance_bias}"

            system_prompt = "你是叙事导演，根据机会信号生成一个戏剧性事件描述。"
            user_prompt = f"""根据以下机会信号生成一个叙事事件：

信号类型: {signal_type}
涉及角色: {agent_names}
发生地点: {location_names[0] if location_names else '某地'}
{will_context}

要求：
- 生成一个2-3句的事件描述
- 体现 {signal_type} 类型的戏剧张力
- 使用中文
- 直接返回描述文本，不要其他内容"""

            raw = await self._cloud.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
                temperature=0.8,
                max_tokens=200,
            )
            description = raw.strip()

        except Exception as e:
            logger.warning(f"[叙事注入] 信号生成失败: {e}")
            description = self._get_default_description(signal_type, agent_names)

        # 创建事件
        event_type_map = {
            "conflict": SystemEventType.CONFLICT,
            "romance": SystemEventType.ROMANCE,
            "cooperation": SystemEventType.COOPERATION,
            "opportunity": SystemEventType.OPPORTUNITY,
        }
        event_type = event_type_map.get(signal_type, SystemEventType.DRAMA_EVENT)

        event = SystemEvent(
            event_id=event_id,
            event_type=event_type,
            description=description,
            affected_agents=list(participants),
            tick=getattr(self._world, '_tick_id', 0),
        )

        self._pending_events.append(event)
        logger.info(f"[叙事注入] 生成叙事事件: {event_id} | {event_type.value} | {description[:50]}...")
        return event

    def _get_default_description(self, signal_type: str, agent_names: list[str]) -> str:
        """获取默认事件描述"""
        name_str = "、".join(agent_names[:2]) if agent_names else "某人"
        defaults = {
            "conflict": f"{name_str}之间发生了激烈的争执，气氛变得紧张起来。",
            "romance": f"{name_str}之间的感情进一步加深，彼此更加亲密了。",
            "cooperation": f"{name_str}开始合作，共同面对挑战。",
            "opportunity": f"{name_str}发现了一个难得的机会。",
        }
        return defaults.get(signal_type, f"{name_str}之间发生了一件事。")

    async def generate_event(
        self,
        llm,
        locations: list[dict],
        agent_names: dict[str, str],
    ) -> Optional[SystemEvent]:
        """生成一个系统事件（LLM辅助，内容由WorldX调度）"""
        tension = self.compute_tension()
        self._event_counter += 1
        event_id = f"sys_{self._event_counter}"

        # 选择事件类型
        if tension < 0.15:
            event_type = SystemEventType.STRANGER_ARRIVES
        elif tension < 0.25:
            event_type = SystemEventType.NEWS_SPREADS
        else:
            event_type = SystemEventType.RUMOR

        # LLM 辅助生成描述
        try:
            location_names = [loc["name"] if isinstance(loc, dict) else str(loc) for loc in locations]
            system_prompt = "你是叙事导演，根据给定的紧张度生成一个简短的事件描述。"
            user_prompt = (
                f"当前 drama_tension={tension:.2f}，事件类型={event_type.value}，"
                f"地点列表={location_names}，角色={list(agent_names.values())}。"
                f"生成一个1-2句的事件描述，使用中文，直接返回描述文本。"
            )
            raw = await llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
                temperature=0.8,
                max_tokens=150,
            )
            description = raw.strip()
        except Exception as e:
            logger.warning(f"[叙事注入] LLM 生成失败: {e}，使用默认描述")
            description = f"一个陌生人出现在{location_names[0] if location_names else '广场'}，引起了大家的注意。"

        affected = list(agent_names.keys())

        event = SystemEvent(
            event_id=event_id,
            event_type=event_type,
            description=description,
            affected_agents=affected,
            tick=len(self._tick_events),
        )
        self._pending_events.append(event)
        logger.info(f"[叙事注入] 生成事件: {event_id} | {event_type.value} | {description[:50]}")
        return event

    async def dispatch_event(self, event: SystemEvent) -> None:
        """
        分发事件给涉及角色
        事件作为 SystemMessage 推入 Agent 的消息队列
        """
        for agent_id in event.affected_agents:
            try:
                agent = self._world.get_agent(agent_id)
                if agent and hasattr(agent, 'receive_system_event'):
                    agent.receive_system_event(event)
                    logger.info(f"[叙事注入] 事件 {event.event_id} 已分发给 {agent_id}")
            except Exception as e:
                logger.error(f"[叙事注入] 事件分发失败 {agent_id}: {e}")

    async def broadcast_drama_event(self, event: SystemEvent) -> None:
        """
        通过 WebSocket 广播戏剧事件
        由 WorldEngine 调用
        """
        if hasattr(self._world, '_broadcast_ws'):
            try:
                await self._world._broadcast_ws({
                    "type": "drama_event",
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "description": event.description,
                    "participants": event.affected_agents,
                    "tick": event.tick,
                })
            except Exception as e:
                logger.error(f"[叙事注入] 广播失败: {e}")

    def pop_pending(self) -> Optional[SystemEvent]:
        """取出最早待处理的事件"""
        if self._pending_events:
            return self._pending_events.pop(0)
        return None

    def get_recent_events(self, count: int = 5) -> list[SystemEvent]:
        return self._pending_events[-count:]

    def as_dict(self) -> dict:
        return {
            "tension": self.compute_tension(),
            "pending_events": [
                {"id": e.event_id, "type": e.event_type.value, "desc": e.description}
                for e in self._pending_events
            ],
        }