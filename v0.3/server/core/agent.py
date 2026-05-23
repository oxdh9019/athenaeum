"""
agent.py — V0.3 Agent 实现
"""

import asyncio
import logging
from typing import Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class V03Agent:
    """
    V0.3 Agent - 封装角色行为和决策
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        personality: dict,
        llm,
        world,
        initial_location: str,
    ):
        self._agent_id = agent_id
        self._name = name
        self._personality = personality
        self._llm = llm
        self._world = world
        self._current_location = initial_location

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        self._short_term_memory: list[tuple[str, str]] = []
        self._max_memory = 20

    @property
    def id(self) -> str:
        return self._agent_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def personality_desc(self) -> str:
        lines = []
        for trait, val in self._personality.items():
            desc = "高" if val > 0.6 else "低"
            lines.append(f"{trait}: {val:.1f}（{desc}）")
        return "\n".join(lines)

    @property
    def needs(self) -> Any:
        if hasattr(self, '_needs'):
            return self._needs
        return None

    def add_memory(self, role: str, content: str) -> None:
        self._short_term_memory.append((role, content))
        if len(self._short_term_memory) > self._max_memory:
            self._short_term_memory.pop(0)

    def get_memory_context(self) -> list[dict]:
        return [{"role": r, "content": c} for r, c in self._short_term_memory[-self._max_memory:]]

    async def decide_action(self, tick_type: str, env_state: dict, neighbors: list[str]) -> Optional[dict]:
        if tick_type == "silent":
            return None

        prompt = self._build_behavior_prompt(env_state, neighbors)

        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个行为决策助手。",
                temperature=0.3,
                max_tokens=100,
            )
            return self._parse_action(response)
        except Exception as e:
            logger.warning(f"[{self._name}] 行为决策失败: {e}")
            return None

    def _build_behavior_prompt(self, env_state: dict, neighbors: list[str]) -> str:
        loc = self._current_location or "未知"
        time_desc = env_state.get("time_of_day", "unknown")
        weather = env_state.get("weather", "unknown")
        neighbor_desc = ", ".join(neighbors) if neighbors else "无"

        return f"""你是 {self._name}，目前在 {loc}。

时间: {time_desc} | 天气: {weather}
附近的人: {neighbor_desc}

请决定下一步行动。输出JSON格式：
{{"action": "move|dialogue|wait", "target": "位置名或角色ID或null"}}

只输出JSON，不要其他内容。"""

    def _parse_action(self, response: str) -> Optional[dict]:
        import json
        import re
        try:
            match = re.search(r'\{[^}]+\}', response)
            if match:
                return json.loads(match.group())
        except json.JSONDecodeError:
            pass
        return {"action": "wait", "target": None}

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
                    if action["action"] == "move" and action["target"]:
                        self._world.move_agent(self._agent_id, action["target"])
                    elif action["action"] == "dialogue":
                        pass

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


class MinimalAgent:
    """
    简化版 Agent - 用于无完整配置的角色
    """

    def __init__(self, agent_id: str, name: str, world, llm, initial_location: str = None):
        self._agent_id = agent_id
        self._name = name
        self._world = world
        self._llm = llm
        self._running = False
        self._needs = None
        self._initial_location = initial_location
        self._personality = None
        self._identity_tags = None
        self._mood = None
        self._intention = None
        self._backstory = None

    @property
    def id(self) -> str:
        return self._agent_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def personality(self):
        return self._personality

    @personality.setter
    def personality(self, value):
        self._personality = value

    @property
    def identity_tags(self):
        return self._identity_tags

    @identity_tags.setter
    def identity_tags(self, value):
        self._identity_tags = value

    @property
    def mood(self):
        return self._mood

    @mood.setter
    def mood(self, value):
        self._mood = value

    @property
    def intention(self):
        return self._intention

    @intention.setter
    def intention(self, value):
        self._intention = value

    @property
    def backstory(self):
        return self._backstory

    @backstory.setter
    def backstory(self, value):
        self._backstory = value

    @property
    def needs(self):
        return self._needs

    @property
    def v02(self):
        class FakeV02:
            needs = self._needs
            personality_desc = "性格随和，喜欢和人交流。"
            memory_context = []
        return FakeV02()

    @property
    def personality_desc(self) -> str:
        return "性格随和，喜欢和人交流。"

    def add_memory(self, role: str, content: str) -> None:
        pass

    def get_memory_context(self) -> list[dict]:
        return []

    def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
