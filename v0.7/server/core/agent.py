"""
agent.py — V0.5 Agent 实现（含记忆系统集成）
V0.3 基础 + V0.5 记忆系统集成
"""

import asyncio
import logging
from typing import Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class V05Agent:
    """
    V0.5 Agent - 封装角色行为、决策和记忆系统
    集成：短期记忆、长期记忆归档、语义检索、遗忘曲线
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        personality: dict,
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
        self._llm = llm  # 用于对话/动作生成（通常是本地 Ollama）
        self._cloud_llm = cloud_llm  # 云端 MiniMax（用于记忆摘要）
        self._local_llm = local_llm  # 本地 Qwen（用于检索/校验）
        self._world = world
        self._current_location = initial_location

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # 短期记忆（V0.3 原有）
        self._short_term_memory: list[tuple[str, str]] = []
        self._max_memory = 20

        # V0.5 记忆系统
        self._archiver = archiver  # MemoryArchiver
        self._retriever = retriever  # MemoryRetriever
        self._forgetting_curve = forgetting_curve  # ForgettingCurve

        # 记录对话用于归档
        self._dialogue_buffer: list[dict] = []

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
    def neuroticism(self) -> float:
        """获取神经质用于遗忘曲线计算"""
        return self._personality.get("neuroticism", 0.5)

    @property
    def needs(self) -> Any:
        if hasattr(self, '_needs'):
            return self._needs
        return None

    # ==================== 性格属性访问器（供 opportunity_detector 使用）====================

    @property
    def empathy(self) -> float:
        """获取同理心属性"""
        if hasattr(self, '_v02') and self._v02:
            return getattr(self._v02, 'empathy', 0.5)
        # 尝试从 personality 扩展性格中获取
        if hasattr(self, '_extended_personality'):
            return self._extended_personality.get('empathy', 0.5)
        return 0.5

    @property
    def ambition(self) -> float:
        """获取野心属性"""
        if hasattr(self, '_v02') and self._v02:
            return getattr(self._v02, 'ambition', 0.5)
        if hasattr(self, '_extended_personality'):
            return self._extended_personality.get('ambition', 0.5)
        return 0.5

    @property
    def courage(self) -> float:
        """获取勇气属性"""
        if hasattr(self, '_v02') and self._v02:
            return getattr(self._v02, 'courage', 0.5)
        if hasattr(self, '_extended_personality'):
            return self._extended_personality.get('courage', 0.5)
        return 0.5

    @property
    def loyalty(self) -> float:
        """获取忠诚属性"""
        if hasattr(self, '_v02') and self._v02:
            return getattr(self._v02, 'loyalty', 0.5)
        if hasattr(self, '_extended_personality'):
            return self._extended_personality.get('loyalty', 0.5)
        return 0.5

    # ==================== 系统事件接收 ====================

    def receive_system_event(self, event) -> None:
        """
        接收来自 NarrativeInjector 的系统事件
        事件作为 SystemMessage 推入外部消息队列
        """
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
        logger.info(f"[{self._name}] 接收系统事件: {message.type} - {message.description[:50]}...")

    # ==================== 记忆系统 ====================

    def add_memory(self, role: str, content: str) -> None:
        """添加短期记忆"""
        self._short_term_memory.append((role, content))
        if len(self._short_term_memory) > self._max_memory:
            self._short_term_memory.pop(0)

    def get_memory_context(self) -> list[dict]:
        """获取短期记忆上下文"""
        return [{"role": r, "content": c} for r, c in self._short_term_memory[-self._max_memory:]]

    def add_dialogue_for_archival(self, dialogue_data: dict) -> None:
        """
        将对话加入归档队列
        dialogue_data: {"from": str, "to": str, "utterance": str, "tick": int}
        """
        self._dialogue_buffer.append(dialogue_data)

        # 记录到短期记忆
        speaker = dialogue_data.get("from", "")
        utterance = dialogue_data.get("utterance", "")
        if speaker and utterance:
            self.add_memory(speaker, utterance)

    async def try_archive(self, current_tick: int, force: bool = False) -> None:
        """
        尝试归档记忆（每10 Tick调用一次）
        """
        if self._archiver and self._dialogue_buffer:
            # 计算待归档数量
            pending_count = len(self._dialogue_buffer)
            if pending_count >= 10 or (force and pending_count > 0):
                summary = await self._archiver.archive_if_needed(self._agent_id, current_tick, force)
                if summary:
                    # 将归档的记忆添加到遗忘曲线
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
        """
        检索相关记忆，返回格式化后的 [RECALL] 文本
        """
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
        """
        标记核心记忆（关系变化 > 0.2 时调用）
        """
        if self._forgetting_curve and related_memory_id:
            self._forgetting_curve.mark_as_core(related_memory_id)

    async def prune_memories(self, current_tick: int) -> None:
        """
        清理过期记忆
        """
        if self._forgetting_curve:
            deleted = self._forgetting_curve.prune_memories(current_tick)
            if deleted:
                logger.info(f"[{self._name}] 删除了 {len(deleted)} 条过期记忆")

    # ==================== 行为决策 ====================

    async def decide_action(self, tick_type: str, env_state: dict, neighbors: list[str]) -> Optional[dict]:
        if tick_type == "silent":
            return None

        # 获取记忆上下文（短期记忆）
        memory_context = self.get_memory_context()

        # 尝试检索长期记忆（如果 retriever 可用）
        recall_section = ""
        if self._retriever and tick_type != "silent":
            # 用意图描述作为 query
            query = f"当前状态: {env_state.get('time_of_day', 'unknown')}, 附近的人: {', '.join(neighbors) or '无'}"
            recall_section = await self.retrieve_memories(query, getattr(self._world, '_tick_id', 0))

        prompt = self._build_behavior_prompt(env_state, neighbors, memory_context, recall_section)

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

        # 构建短期记忆文本
        memory_text = ""
        if memory_context:
            memory_lines = [f"- {m['role']}: {m['content']}" for m in memory_context[-5:]]
            memory_text = "\n最近记忆:\n" + "\n".join(memory_lines)

        return f"""你是 {self._name}，目前在 {loc}。

时间: {time_desc} | 天气: {weather}
附近的人: {neighbor_desc}
{memory_text}
{recall_section}

请决定下一步行动。输出JSON格式：
{{"action": "move|dialogue|wait", "target": "位置名或角色ID或null"}}

只输出JSON，不要其他内容。"""

    def _parse_action(self, response: str) -> Optional[dict]:
        from utils.llm_parsing import parse_llm_json
        result = parse_llm_json(response)
        if result is not None and "action" in result:
            return result
        return {"action": "wait", "target": None}

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
                    if action["action"] == "move" and action["target"]:
                        self._world.move_agent(self._agent_id, action["target"])
                    elif action["action"] == "dialogue":
                        pass

                # V0.5: 每10 Tick 尝试归档记忆
                current_tick = getattr(self._world, '_tick_id', 0)
                if current_tick > 0 and current_tick % 10 == 0:
                    await self.try_archive(current_tick)

                # V0.5: 每次 Tick 清理过期记忆
                await self.prune_memories(current_tick)

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
    简化版 Agent - 用于无完整配置的角色（V0.5 版本）
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

        # V0.5 简化记忆
        self._short_term_memory: list[tuple[str, str]] = []
        self._dialogue_buffer: list[dict] = []

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

    @property
    def neuroticism(self) -> float:
        """获取神经质用于遗忘曲线"""
        if self._personality and isinstance(self._personality, dict):
            return self._personality.get("neuroticism", 0.5)
        return 0.5

    def add_memory(self, role: str, content: str) -> None:
        self._short_term_memory.append((role, content))
        if len(self._short_term_memory) > 20:
            self._short_term_memory.pop(0)

    def get_memory_context(self) -> list[dict]:
        return [{"role": r, "content": c} for r, c in self._short_term_memory[-20:]]

    def add_dialogue_for_archival(self, dialogue_data: dict) -> None:
        """将对话加入归档队列"""
        self._dialogue_buffer.append(dialogue_data)
        speaker = dialogue_data.get("from", "")
        utterance = dialogue_data.get("utterance", "")
        if speaker and utterance:
            self.add_memory(speaker, utterance)

    def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False