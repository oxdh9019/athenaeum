"""
dialogue_engine.py — V0.2 对话循环引擎
ADR-001 (结构化意图) + ADR-002 (消息队列) + ADR-003 (需求队列)
+ 循环检测 + 关系演化 + 用户附身
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from messages import IntentMessage, DialogueMessage, IntentType, Emotion
from needs import NeedQueue
from intent_generator import IntentGenerator
from dialogue_generator import DialogueGenerator

logger = logging.getLogger(__name__)

# 关系演化规则表: (intent_type, emotion) → delta
RELATIONSHIP_DELTA = {
    (IntentType.SHARE, Emotion.WARM): +0.05,
    (IntentType.SHARE, Emotion.CURIOUS): +0.03,
    (IntentType.GREET, Emotion.WARM): +0.02,
    (IntentType.ASK, Emotion.CURIOUS): +0.02,
    (IntentType.INVITE, Emotion.WARM): +0.04,
    (IntentType.INVITE, Emotion.NEUTRAL): +0.02,
    (IntentType.FLEE, Emotion.WARY): -0.08,
    (IntentType.FLEE, Emotion.ANXIOUS): -0.05,
    (IntentType.CHANGE_TOPIC, Emotion.NEUTRAL): 0.0,
}


@dataclass
class Relationship:
    """两角色间的关系"""
    agent_a: str
    agent_b: str
    strength: float = 0.5  # -1.0 ~ 1.0

    def evolve(self, intent: IntentMessage, emotion: Emotion) -> float:
        key = (intent.intent_type, emotion)
        delta = RELATIONSHIP_DELTA.get(key, 0.0)
        self.strength = max(-1.0, min(1.0, self.strength + delta))
        return delta


@dataclass
class DialogueTurn:
    """记录一轮对话"""
    turn_num: int
    speaker_id: str
    speaker_name: str
    intent: IntentMessage
    dialogue: DialogueMessage
    relationship_delta: float = 0.0


@dataclass
class ConversationStats:
    """统计报告"""
    total_turns: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    turns: list[DialogueTurn] = field(default_factory=list)
    relationship_changes: list[tuple[str, str, float]] = field(default_factory=list)

    def add_turn(self, turn: DialogueTurn):
        self.turns.append(turn)
        self.total_turns += 1

    def add_rel_change(self, a: str, b: str, delta: float):
        self.relationship_changes.append((a, b, delta))

    def report(self) -> str:
        lines = [
            "\n" + "=" * 50,
            "  对话统计报告",
            "=" * 50,
            f"  总对话轮次: {self.total_turns}",
            f"  总Token: {self.total_tokens}",
            f"  总成本: ${self.total_cost:.4f}",
            "",
            "  关系变化:",
        ]
        for a, b, delta in self.relationship_changes:
            sign = "+" if delta >= 0 else ""
            lines.append(f"    {a} ↔ {b}: {sign}{delta:.3f}")
        lines.append("=" * 50)
        return "\n".join(lines)


class DialogueEngine:
    """
    双 Agent 对话引擎

    架构:
    - 单一 asyncio.Queue 作为对话总线，所有消息通过它路由
    - 明确的 next_speaker 跟踪，解决队列方向混淆问题
    - 每轮：当前发言者思考 → 生成意图+对话 → 推入队列 → 切换发言者

    possession 处理:
    - 附身时，下一轮由用户接管，用户输入直接作为 dialogue
    - 附身轮的意图使用 override，emotion 由对话内容推导
    """

    def __init__(
        self,
        agent_a,
        agent_b,
        intent_generator: IntentGenerator,
        dialogue_generator: DialogueGenerator,
        max_turns: int = 20,
        loop_threshold: float = 0.7,
        loop_window: int = 3,
        st_cache_dir: Optional[str] = None,
    ):
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.intent_gen = intent_generator
        self.diag_gen = dialogue_generator
        self.max_turns = max_turns
        self.loop_threshold = loop_threshold
        self.loop_window = loop_window
        self.st_cache_dir = st_cache_dir  # sentence-transformers 缓存路径

        # 统一对话队列（EventBus 雏形）
        self.queue: asyncio.Queue[DialogueMessage] = asyncio.Queue()

        # 关系
        self.relationship = Relationship(agent_a.id, agent_b.id, strength=0.6)

        # 对话历史（用于循环检测和意图生成上下文）
        self.conversation_log: list[DialogueMessage] = []

        # 统计
        self.stats = ConversationStats()

        # 轮次控制
        self._turn_count = 0
        self._running = False

        # 附身状态
        self._possessed_id: Optional[str] = None        # 被附身的 Agent ID
        self._possess_msg: Optional[str] = None        # 用户注入的消息
        self._possess_intent: Optional[dict] = None    # 用户注入的意图
        self._possess_event: asyncio.Event = asyncio.Event()  # 附身触发事件，可中断等待

        # 下一位发言者
        self._next_speaker_id: str = agent_a.id

    # ── 附身 API ──────────────────────────────────────────────────────────

    def possess(self, agent_id: str, user_message: str, intent_override: Optional[dict] = None):
        """用户附身指定 Agent，立即触发事件以中断等待"""
        if agent_id not in (self.agent_a.id, self.agent_b.id):
            raise ValueError(f"未知 Agent ID: {agent_id}")
        self._possessed_id = agent_id
        self._possess_msg = user_message
        self._possess_intent = intent_override
        self._possess_event.set()
        logger.info(f"[用户附身] {agent_id}: {user_message}")

    def release(self):
        """退出附身模式"""
        self._possessed_id = None
        self._possess_msg = None
        self._possess_intent = None
        self._possess_event.clear()
        logger.info("[用户退出附身]")

    @property
    def is_possessed(self) -> bool:
        return self._possessed_id is not None

    # ── 工具 ──────────────────────────────────────────────────────────────

    def _speaker(self, agent_id: str):
        """根据 ID 返回 Agent 实例"""
        if agent_id == self.agent_a.id:
            return self.agent_a
        return self.agent_b

    def _listener(self, speaker_id: str):
        """根据发言者 ID 返回监听者实例"""
        return self._speaker(self.agent_b.id if speaker_id == self.agent_a.id else self.agent_a.id)

    def _speaker_name(self, agent_id: str) -> str:
        return self._speaker(agent_id).name

    # ── 可中断等待 ─────────────────────────────────────────────────────────

    async def _wait_for_next(self) -> tuple[Optional[DialogueMessage], bool]:
        """
        等待队列消息或附身事件。

        返回:
            (dialogue_message, was_possessed)
            - was_possessed=True 时，dialogue_message 为注入的占位消息，
              实际对话内容由 _do_turn() 用 _possess_msg 替代
        """
        # 同时等待队列消息和附身事件
        pending_get = asyncio.create_task(self.queue.get())
        pending_possess = asyncio.create_task(self._possess_event.wait())

        try:
            done, pending = await asyncio.wait(
                [pending_get, pending_possess],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            return None, False

        # 取消未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self._possess_event.is_set():
            # 附身事件触发：清除事件（_do_turn 中会处理附身逻辑）
            self._possess_event.clear()
            # 返回 None 表示本轮应由用户接管
            return None, True

        # 正常队列消息
        return done.pop().result(), False

    # ── 循环检测 ──────────────────────────────────────────────────────────

    async def _is_looping(self) -> bool:
        """检测语义循环"""
        if len(self.conversation_log) < self.loop_window * 2:
            return False

        try:
            from embedding_ollama import OllamaEmbedder
            
            embedder = OllamaEmbedder(model="bge-m3")
            
            recent = [d.utterance for d in self.conversation_log[-self.loop_window * 2:]]
            embeddings = embedder.encode(recent, normalize_embeddings=True)
            
            if not embeddings or len(embeddings) < 2:
                return False
                
        except Exception as e:
            logger.warning(f"无法使用 Ollama 嵌入，跳过循环检测: {e}")
            return False

        similarities = [
            sum(a * b for a, b in zip(embeddings[i], embeddings[i + 1]))
            for i in range(len(embeddings) - 1)
        ]
        avg_sim = sum(similarities) / len(similarities)
        logger.info(f"[循环检测] 最近{len(similarities)}对相似度: {avg_sim:.3f} (阈值: {self.loop_threshold})")
        return avg_sim > self.loop_threshold

    # ── 单轮对话 ──────────────────────────────────────────────────────────

    async def _do_turn(self) -> DialogueMessage:
        """
        执行一轮对话：当前发言者思考 → 生成意图 → 生成对话 → 入队
        返回生成的 DialogueMessage。
        """
        speaker = self._speaker(self._next_speaker_id)
        listener = self._listener(self._next_speaker_id)
        self._turn_count += 1

        logger.debug(f"[回合 {self._turn_count}] 发言者: {speaker.name}")

        # ── 1. 意图生成 ────────────────────────────────────────────────

        intent_override: Optional[dict] = None

        if self._possessed_id == speaker.id and self._possess_msg:
            # 用户附身注入
            intent_override = self._possess_intent or {
                "intent_type": "share",
                "target": listener.id,
                "reasoning": f"用户附身: {self._possess_msg}",
                "urgency": 0.9,
                "emotion": "neutral",
            }

        elif await self._is_looping():
            logger.warning("[循环检测] 强制 change_topic")
            intent_override = {
                "intent_type": "change_topic",
                "target": listener.id,
                "reasoning": "检测到对话陷入循环，主动转换话题",
                "urgency": 0.8,
                "emotion": "neutral",
            }

        intent = await self.intent_gen.generate(
            agent_id=speaker.id,
            agent_name=speaker.name,
            personality_desc=speaker.personality_desc,
            needs=speaker.needs,
            memory_context=speaker.memory_context,
            recent_dialogue=self._conversation_as_dict(),
            other_agent_name=listener.name,
            other_agent_id=listener.id,
            override_intent=intent_override,
        )

        speaker.needs.update_from_environment(intent.reasoning)

        # ── 2. 对话生成 ────────────────────────────────────────────────

        override_speech: Optional[str] = None
        if self._possessed_id == speaker.id and self._possess_msg:
            override_speech = self._possess_msg

        dialogue = await self.diag_gen.generate(
            intent=intent,
            agent_id=speaker.id,
            agent_name=speaker.name,
            agent_personality_desc=speaker.personality_desc,
            relationship=self.relationship.strength,
            memory_context=speaker.memory_context,
            other_agent_name=listener.name,
            override_speech=override_speech,
        )

        # ── 3. 记忆更新 ────────────────────────────────────────────────

        speaker.add_memory("user" if speaker.id == self.agent_a.id else "assistant",
                           f"[{listener.name}]: {dialogue.utterance}")
        speaker.add_memory("assistant" if speaker.id == self.agent_a.id else "user",
                           f"[{speaker.name}]: {dialogue.utterance}")

        # ── 4. 关系演化 ────────────────────────────────────────────────

        delta = self.relationship.evolve(intent, dialogue.emotion_tag)
        self.stats.add_rel_change(speaker.id, listener.id, delta)
        self.stats.add_turn(DialogueTurn(
            turn_num=self._turn_count,
            speaker_id=speaker.id,
            speaker_name=speaker.name,
            intent=intent,
            dialogue=dialogue,
            relationship_delta=delta,
        ))
        self.conversation_log.append(dialogue)

        # ── 5. 切换发言者 ──────────────────────────────────────────────

        self._next_speaker_id = (
            self.agent_a.id if self._next_speaker_id == self.agent_b.id
            else self.agent_b.id
        )

        # ── 6. 推入队列 ────────────────────────────────────────────────

        await self.queue.put(dialogue)
        
        # 直接输出到终端
        print(f"\033[1;34m{speaker.name}:\033[0m {dialogue.utterance}")
        logger.info(f"[{speaker.name}]: {dialogue.utterance[:60]} | 意图: {intent.intent_type.value} | 关系变化: {delta:+.3f}")

        return dialogue

    # ── 主循环 ─────────────────────────────────────────────────────────────

    async def run(self) -> ConversationStats:
        """
        启动对话循环。

        流程:
        1. Agent A 开场问候 → 入队
        2. 循环（直到 max_turns 或用户退出）:
           - 从队列取出消息（对方刚才说的）
           - 当前发言者执行 _do_turn()
        """
        self._running = True
        self._next_speaker_id = self.agent_a.id

        logger.info(f"[对话引擎启动] {self.agent_a.name} ↔ {self.agent_b.name} | 最大轮次: {self.max_turns}")

        # ── 开场：Agent A 主动问候 ──────────────────────────────────────

        greeting_intent = IntentMessage(
            tick=0,
            agent_id=self.agent_a.id,
            intent_type=IntentType.GREET,
            target=self.agent_b.id,
            reasoning=f"{self.agent_a.name} 主动向老朋友 {self.agent_b.name} 打招呼",
            urgency=0.5,
            emotion=Emotion.WARM,
        )

        greeting_dialogue = await self.diag_gen.generate(
            intent=greeting_intent,
            agent_id=self.agent_a.id,
            agent_name=self.agent_a.name,
            agent_personality_desc=self.agent_a.personality_desc,
            relationship=self.relationship.strength,
            memory_context=self.agent_a.memory_context,
            other_agent_name=self.agent_b.name,
        )

        await self.queue.put(greeting_dialogue)
        self._next_speaker_id = self.agent_b.id
        self._turn_count = 1

        self.stats.add_turn(DialogueTurn(
            turn_num=0,
            speaker_id=self.agent_a.id,
            speaker_name=self.agent_a.name,
            intent=greeting_intent,
            dialogue=greeting_dialogue,
        ))
        self.conversation_log.append(greeting_dialogue)

        # 直接输出到终端
        print(f"\033[1;34m{self.agent_a.name}:\033[0m {greeting_dialogue.utterance}")
        logger.info(f"[开场] {self.agent_a.name}: {greeting_dialogue.utterance[:60]}")

        # ── 主循环 ─────────────────────────────────────────────────────

        while self._running and self._turn_count <= self.max_turns:
            # 可中断的等待：队列消息 或 附身事件
            incoming, was_possessed = await self._wait_for_next()

            if was_possessed:
                await self._do_turn()
                continue

            if incoming is None:
                logger.warning("队列等待超时，结束对话")
                print("\n[系统] 对话超时，自动结束")
                break

            # 检查退出命令
            if incoming.utterance.strip().lower() in ("/quit", "/exit"):
                logger.info("收到退出命令")
                break

            # 执行当前轮
            await self._do_turn()

        # ── 收尾统计 ───────────────────────────────────────────────────

        self.stats.total_tokens = (
            self.agent_a.total_tokens + self.agent_b.total_tokens
        )
        self.stats.total_cost = (
            self.agent_a.total_cost + self.agent_b.total_cost
        )

        logger.info(f"[对话引擎结束] 总轮次: {self._turn_count}")
        return self.stats

    def _conversation_as_dict(self) -> list[dict]:
        return [
            {
                "from": d.from_agent,
                "to": d.to_agent,
                "utterance": d.utterance,
                "emotion": d.emotion_tag.value,
            }
            for d in self.conversation_log[-6:]
        ]