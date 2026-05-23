"""
default_plugins.py — V0.3 默认插件实现
"""

import asyncio
import logging
from typing import Optional, Any
from dataclasses import dataclass

from .interfaces import (
    IDesireEngine, IMemorySystem, ILLMClient, IEventBus,
    ISpaceSystem, INarrativeEngine, IScheduler, TickType
)

logger = logging.getLogger(__name__)


@dataclass
class Need:
    name: str
    level: float = 0.5
    target: Optional[str] = None

    def is_active(self, threshold: float = 0.6) -> bool:
        return self.level >= threshold

    def satisfy(self, delta: float):
        self.level = max(0.0, self.level - delta)

    def increase(self, delta: float):
        self.level = min(1.0, self.level + delta)


class DefaultDesireEngine(IDesireEngine):
    """默认欲望引擎实现"""

    def __init__(self):
        self._agent_needs: dict[str, dict[str, Need]] = {}

    def register_agent(self, agent_id: str) -> None:
        if agent_id not in self._agent_needs:
            self._agent_needs[agent_id] = {
                "safety": Need(name="safety", level=0.2),
                "belonging": Need(name="belonging", level=0.4),
                "novelty": Need(name="novelty", level=0.5),
            }

    def get_active_needs(self, agent_id: str) -> list[Any]:
        if agent_id not in self._agent_needs:
            return []
        return [n for n in self._agent_needs[agent_id].values() if n.is_active()]

    def get_top_need(self, agent_id: str) -> Optional[Any]:
        if agent_id not in self._agent_needs:
            return None
        needs = self._agent_needs[agent_id]
        active = [n for n in needs.values() if n.is_active()]
        if not active:
            return max(needs.values(), key=lambda n: n.level)
        return max(active, key=lambda n: n.level)

    def update_from_environment(self, agent_id: str, event_text: str) -> None:
        if agent_id not in self._agent_needs:
            return
        needs = self._agent_needs[agent_id]
        text = event_text.lower()
        if any(k in text for k in ["危险", "害怕", "threat", "fear", "storm", "冲突"]):
            needs["safety"].increase(0.15)
        if any(k in text for k in ["一个人", "孤独", "没人", "alone"]):
            needs["belonging"].increase(0.1)
        if any(k in text for k in ["一样", "重复", "无聊", "same"]):
            needs["novelty"].increase(0.1)

    def update_from_interaction(self, agent_id: str, intent_type: str, emotion: str, positive: bool) -> None:
        if agent_id not in self._agent_needs:
            return
        needs = self._agent_needs[agent_id]
        if positive:
            needs["belonging"].satisfy(0.08)
        else:
            needs["belonging"].increase(0.05)
        if intent_type in ["ask", "share"]:
            needs["novelty"].satisfy(0.05)

    def as_prompt_fragment(self, agent_id: str) -> str:
        if agent_id not in self._agent_needs:
            return "无需求信息"
        lines = ["## 当前需求状态"]
        for name, need in self._agent_needs[agent_id].items():
            status = "渴望" if need.is_active() else "满足"
            target = f"（目标: {need.target}）" if need.target else ""
            lines.append(f"- {name}: {need.level:.2f} [{status}] {target}")
        return "\n".join(lines)


class DefaultMemorySystem(IMemorySystem):
    """默认记忆系统实现 - 短期记忆窗口"""

    def __init__(self, max_short_term: int = 20):
        self._max_short_term = max_short_term
        self._short_term: dict[str, list[tuple[str, str]]] = {}
        self._long_term: dict[str, list[dict]] = {}

    def add_short_term(self, agent_id: str, role: str, content: str) -> None:
        if agent_id not in self._short_term:
            self._short_term[agent_id] = []
        self._short_term[agent_id].append((role, content))
        if len(self._short_term[agent_id]) > self._max_short_term:
            self._short_term[agent_id].pop(0)

    def get_context(self, agent_id: str, limit: int = 20) -> list[dict]:
        if agent_id not in self._short_term:
            return []
        memories = self._short_term[agent_id][-limit:]
        return [{"role": r, "content": c} for r, c in memories]

    async def summarize_and_store_long_term(self, agent_id: str, llm: ILLMClient) -> None:
        if agent_id not in self._short_term or not self._short_term[agent_id]:
            return
        memories = self._short_term[agent_id]
        summary_prompt = "请简要总结以下对话要点（不超过50字）：\n" + "\n".join(
            f"{r}: {c}" for r, c in memories[-10:]
        )
        try:
            summary = await llm.chat([{"role": "user", "content": summary_prompt}],
                                    temperature=0.3, max_tokens=100)
            if agent_id not in self._long_term:
                self._long_term[agent_id] = []
            self._long_term[agent_id].append({
                "content": summary,
                "tick": 0,
                "access_count": 1
            })
        except Exception as e:
            logger.error(f"记忆摘要失败: {e}")

    async def retrieve_relevant(self, agent_id: str, query: str, limit: int = 5) -> list[dict]:
        return []

    def decay_long_term(self, decay_factor: float = 0.95) -> None:
        for memories in self._long_term.values():
            for m in memories:
                m["access_count"] *= decay_factor


class DefaultEventBus(IEventBus):
    """默认事件总线实现"""

    def __init__(self):
        self._subscribers: dict[str, list] = {}

    async def publish(self, event_type: str, data: dict) -> None:
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"事件回调失败 [{event_type}]: {e}")

    async def subscribe(self, event_type: str, callback) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def unsubscribe(self, event_type: str, callback) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)


class DefaultSpaceSystem(ISpaceSystem):
    """默认空间系统实现"""

    def __init__(self):
        self._locations: dict[str, dict] = {}
        self._agent_locations: dict[str, str] = {}

    def register_location(self, location_id: str, name: str, tags: list[str], capacity: int) -> None:
        self._locations[location_id] = {
            "id": location_id,
            "name": name,
            "tags": tags,
            "capacity": capacity,
        }

    def get_location(self, agent_id: str) -> Optional[str]:
        return self._agent_locations.get(agent_id)

    def move_agent(self, agent_id: str, target_location: str) -> bool:
        if target_location not in self._locations:
            return False
        loc = self._locations[target_location]
        current_count = sum(1 for loc_id in self._agent_locations.values() if loc_id == target_location)
        if current_count >= loc["capacity"]:
            return False
        self._agent_locations[agent_id] = target_location
        return True

    def get_neighbors(self, agent_id: str) -> list[str]:
        current_loc = self._agent_locations.get(agent_id)
        if not current_loc:
            return []
        return [
            other_id for other_id, loc_id in self._agent_locations.items()
            if loc_id == current_loc and other_id != agent_id
        ]

    def get_location_capacity(self, location: str) -> int:
        if location not in self._locations:
            return 0
        return self._locations[location]["capacity"]


class DefaultNarrativeEngine(INarrativeEngine):
    """默认叙事引擎实现"""

    def __init__(self):
        self._timeline: list[dict] = []
        self._event_types = [
            "神秘物品出现", "谣言传播", "节日庆典", "突发天气变化",
            "陌生访客", "意外相遇", "秘密揭露"
        ]

    async def generate_event(self, world_state: dict) -> Optional[dict]:
        import random
        if random.random() > 0.1:
            return None
        event = {
            "type": random.choice(self._event_types),
            "tick": world_state.get("tick", 0),
            "location": world_state.get("location", "未知"),
            "description": "世界正在发生一些事情...",
        }
        self._timeline.append(event)
        return event

    def get_story_timeline(self) -> list[dict]:
        return self._timeline

    def calculate_stage_momentum(self, location: str, agent_count: int, relationship_complexity: float) -> float:
        base = 0.1
        if agent_count > 2:
            base += 0.2
        if relationship_complexity > 0.5:
            base += 0.3
        return min(1.0, base)


class DefaultScheduler(IScheduler):
    """默认调度器实现 - 分级Tick"""

    def __init__(self, silent_tick_ratio: float = 0.7):
        self._silent_tick_ratio = silent_tick_ratio

    def evaluate_tick_type(self, world_state: dict) -> TickType:
        has_active_need = world_state.get("has_active_need", False)
        has_neighbors = world_state.get("has_neighbors", False)
        if has_active_need or has_neighbors:
            return TickType.NORMAL
        if has_active_need and has_neighbors:
            return TickType.CRITICAL
        return TickType.SILENT

    def should_process_agent(self, agent_id: str, tick_type: TickType) -> bool:
        if tick_type == TickType.SILENT:
            return False
        return True
