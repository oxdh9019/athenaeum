"""
dialogue_engine.py — V0.5 对话引擎
V0.3 基础 + V0.5 记忆系统集成
双Agent交替对话，支持用户附身，集成长期记忆归档和检索
"""

import asyncio
import logging
import re
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class IntentType:
    GREET = "greet"
    SHARE = "share"
    ASK = "ask"
    INVITE = "invite"
    FLEE = "flee"
    CHANGE_TOPIC = "change_topic"
    WAIT = "wait"


class Emotion:
    WARM = "warm"
    CURIOUS = "curious"
    NEUTRAL = "neutral"
    WARY = "wary"
    ANXIOUS = "anxious"


@dataclass
class IntentMessage:
    tick: int
    agent_id: str
    intent_type: str
    target: str
    reasoning: str
    urgency: float
    emotion: str


@dataclass
class DialogueMessage:
    from_agent: str
    to_agent: str
    utterance: str
    emotion_tag: str
    intent_type: str
    micro_action: str = None  # V0.7: 微观动作，如"抿了口茶"


RELATIONSHIP_DELTA = {
    (IntentType.SHARE, Emotion.WARM): 0.05,
    (IntentType.SHARE, Emotion.CURIOUS): 0.03,
    (IntentType.GREET, Emotion.WARM): 0.02,
    (IntentType.ASK, Emotion.CURIOUS): 0.02,
    (IntentType.INVITE, Emotion.WARM): 0.04,
    (IntentType.FLEE, Emotion.WARY): -0.08,
    (IntentType.SHARE, Emotion.WARY): -0.03,
    (IntentType.ASK, Emotion.WARY): -0.02,
}


@dataclass
class Relationship:
    agent_a: str
    agent_b: str
    strength: float = 0.5

    def evolve(self, intent_type: str, emotion: str) -> float:
        key = (intent_type, emotion)
        delta = RELATIONSHIP_DELTA.get(key, 0.0)
        self.strength = max(-1.0, min(1.0, self.strength + delta))
        return delta


class DialogueSession:
    """
    单个对话会话，管理两个Agent之间的对话
    V0.5: 集成记忆归档和检索
    """

    def __init__(
        self,
        agent_a_id: str,
        agent_b_id: str,
        agent_names: dict[str, str],
        llm,
        world=None,
        max_turns: int = 20,
        archiver=None,
        retriever=None,
        router=None,
    ):
        self.agent_a = agent_a_id
        self.agent_b = agent_b_id
        self.agent_names = agent_names
        self._world = world

        self._llm = llm
        self.max_turns = max_turns

        self._queue_a: asyncio.Queue[DialogueMessage] = asyncio.Queue()
        self._queue_b: asyncio.Queue[DialogueMessage] = asyncio.Queue()

        self.relationship = Relationship(agent_a_id, agent_b_id, strength=0.6)

        self.conversation_log: list[DialogueMessage] = []
        self._turn_count = 0
        self._running = False

        self._possessed_id: Optional[str] = None
        self._possess_msg: Optional[str] = None
        self._possess_event = asyncio.Event()

        self._next_speaker = agent_a_id

        # V0.5 记忆系统
        self._archiver = archiver  # MemoryArchiver
        self._retriever = retriever  # MemoryRetriever

        # V0.7 模型路由器
        self._router = router

    def _get_llm_for_purpose(self, purpose: str, is_possessed: bool = False):
        """
        V0.7: 根据 purpose 通过路由器选择 LLM 客户端
        """
        if not self._router:
            return self._llm
        model_key = self._router.route(purpose, is_possessed=is_possessed)
        # model_key is "local" or "cloud"
        if model_key == "cloud":
            from core.plugin_registry import PluginRegistry
            client = PluginRegistry.get_llm_client("cloud")
            if client:
                return client
        return self._llm

    def possess(self, agent_id: str, message: str) -> None:
        if agent_id not in (self.agent_a, self.agent_b):
            raise ValueError(f"Unknown agent: {agent_id}")
        self._possessed_id = agent_id
        self._possess_msg = message
        self._possess_event.set()
        logger.info(f"[Possess] {agent_id}: {message}")

    def release(self) -> None:
        self._possessed_id = None
        self._possess_msg = None
        self._possess_event.clear()

    async def run(self) -> dict:
        self._running = True
        self._next_speaker = self.agent_a

        await self._opening_greeting()

        while self._running and self._turn_count < self.max_turns:
            await asyncio.sleep(0.5)
            self._turn_count += 1
            await self._do_turn()

        return {
            "total_turns": self._turn_count,
            "relationship": self.relationship.strength,
        }

    def stop(self) -> None:
        """停止对话会话（用于暂停引擎）"""
        self._running = False

    async def _opening_greeting(self) -> None:
        greeting = DialogueMessage(
            from_agent=self.agent_a,
            to_agent=self.agent_b,
            utterance=f"你好，{self.agent_names.get(self.agent_b, '朋友')}！",
            emotion_tag=Emotion.WARM,
            intent_type=IntentType.GREET,
        )
        await self._queue_a.put(greeting)
        self.conversation_log.append(greeting)
        self._next_speaker = self.agent_b
        self._turn_count = 1

        # 记录开场到世界状态
        if self._world:
            tick = self._world._tick_id if hasattr(self._world, '_tick_id') else 0
            await self._world.add_dialogue({
                "from": self.agent_names.get(self.agent_a, self.agent_a),
                "from_id": self.agent_a,
                "to": self.agent_names.get(self.agent_b, self.agent_b),
                "utterance": greeting.utterance,
                "tick": tick,
            })
            # V0.5: 加入归档队列
            self._add_to_archival(self.agent_a, self.agent_b, greeting.utterance, tick)

    async def _do_turn(self) -> None:
        speaker_id = self._next_speaker
        listener_id = self.agent_b if speaker_id == self.agent_a else self.agent_a

        speaker_name = self.agent_names.get(speaker_id, speaker_id)
        listener_name = self.agent_names.get(listener_id, listener_id)

        speaker_agent = self._speaker_agent(speaker_id)
        if not speaker_agent:
            return

        override_speech = None
        if self._possess_event.is_set() and self._possessed_id == speaker_id:
            self._possess_event.clear()
            override_speech = self._possess_msg
            self._possessed_id = None
            self._possess_msg = None

        # 步骤1：生成结构化意图（ADR-001）
        intent = await self._generate_intent(
            speaker_id, speaker_name, listener_id, listener_name,
            speaker_agent, override_speech is not None
        )

        if override_speech:
            intent_type = IntentType.SHARE
            emotion_tag = Emotion.NEUTRAL
        else:
            intent_type = intent.intent_type
            emotion_tag = intent.emotion

        # 步骤2：基于意图生成对话（带记忆检索）
        dialogue = await self._generate_dialogue(
            speaker_id, speaker_name, listener_id, listener_name,
            speaker_agent, override_speech, intent
        )

        self.conversation_log.append(dialogue)

        if speaker_id == self.agent_a:
            await self._queue_a.put(dialogue)
        else:
            await self._queue_b.put(dialogue)

        # 步骤3：演化关系值
        previous_strength = self.relationship.strength
        delta = self.relationship.evolve(intent_type, emotion_tag)
        logger.info(f"[Dialogue] {speaker_name}: {dialogue.utterance[:50]}... | {intent_type} | Δ={delta:+.2f}")

        # V0.5: 检查关系变化幅度，标记核心记忆
        if abs(delta) > 0.2:
            logger.info(f"[Memory] 关系变化 {delta:+.2f}，标记核心记忆")
            if speaker_agent and hasattr(speaker_agent, 'mark_core_memory'):
                speaker_agent.mark_core_memory()

        # 记录到世界状态
        if self._world:
            tick = self._world._tick_id if hasattr(self._world, '_tick_id') else 0
            await self._world.add_dialogue({
                "from": speaker_name,
                "from_id": speaker_id,
                "to": listener_name,
                "utterance": dialogue.utterance,
                "tick": tick,
            })
            # V0.5: 加入归档队列
            self._add_to_archival(speaker_id, listener_id, dialogue.utterance, tick)

        self._next_speaker = listener_id

    def _add_to_archival(self, from_id: str, to_id: str, utterance: str, tick: int) -> None:
        """V0.5: 将对话加入归档队列"""
        if self._archiver:
            speaker_name = self.agent_names.get(from_id, from_id)
            self._archiver.queue_for_archival(
                from_id,
                {"from": speaker_name, "to": self.agent_names.get(to_id, to_id), "utterance": utterance, "tick": tick}
            )

    async def _generate_intent(
        self,
        speaker_id: str,
        speaker_name: str,
        listener_id: str,
        listener_name: str,
        speaker_agent: Any,
        is_possessed: bool = False,
    ) -> IntentMessage:
        """步骤1：生成结构化意图（ADR-001）"""
        # V0.5: 检索相关记忆
        recall_section = ""
        if self._retriever and speaker_agent:
            current_tick = getattr(self._world, '_tick_id', 0) if self._world else 0
            neuroticism = getattr(speaker_agent, 'neuroticism', 0.5)
            query = f"与{listener_name}的对话交流"
            memories = await self._retriever.retrieve(
                agent_id=speaker_id,
                query_text=query,
                current_tick=current_tick,
                neuroticism=neuroticism,
            )
            if memories:
                recall_lines = []
                for mem in memories:
                    recall_lines.append(f"- {mem.content}")
                    if mem.emotion != "neutral":
                        recall_lines.append(f"  （记忆情感：{mem.emotion}）")
                recall_section = "\n[RECALL] 相关记忆：\n" + "\n".join(recall_lines) + "\n[/RECALL]"

        # 获取角色背景信息
        speaker_info = ""
        if speaker_agent:
            if hasattr(speaker_agent, 'personality') and speaker_agent.personality:
                p = speaker_agent.personality
                if isinstance(p, dict):
                    speaker_info += f"性格特点：O={p.get('openness', 0.5)}, C={p.get('conscientiousness', 0.5)}, E={p.get('extraversion', 0.5)}, A={p.get('agreeableness', 0.5)}, N={p.get('neuroticism', 0.5)}\n"
                else:
                    speaker_info += f"性格特点：O={p.openness}, C={p.conscientiousness}, E={p.extraversion}, A={p.agreeableness}, N={p.neuroticism}\n"
            if hasattr(speaker_agent, 'identity_tags') and speaker_agent.identity_tags:
                speaker_info += f"身份标签：{speaker_agent.identity_tags.get('primary', '')}\n"
            if hasattr(speaker_agent, 'mood') and speaker_agent.mood:
                speaker_info += f"当前心情：{speaker_agent.mood}\n"

        recent_context = "\n".join([
            f"{self.agent_names.get(d.from_agent, d.from_agent)}: {d.utterance}"
            for d in self.conversation_log[-6:]
        ]) if self.conversation_log else "（暂无历史对话）"

        prompt = f"""你是 {speaker_name}（ID: {speaker_id}），正在和 {listener_name} 交谈。

## 身份信息
{speaker_info}

## 当前对话历史
{recent_context}

{recall_section}

## 你的任务
请为 {speaker_name} 选择下一个对话意图。

意图类型说明:
- greet: 打招呼、开启对话
- ask: 向对方提问、寻求信息
- share: 分享自己的经历、想法或感受
- invite: 邀请对方参与某事
- flee: 回避、退出现有对话
- wait: 保持沉默或观察
- change_topic: 主动转换话题，打破僵局

请严格按以下 JSON 格式输出（不要输出任何其他内容）：
{{"intent_type": "意图类型", "target": "{listener_id}", "reasoning": "你的自然语言内部独白", "urgency": 0.0到1.0之间", "emotion": "warm|anxious|curious|neutral|wary"}}
"""

        try:
            llm = self._get_llm_for_purpose("intent_decision", is_possessed)
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )

            import json
            text = response.strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    raise ValueError("无法解析意图JSON")

            intent_type_str = data.get("intent_type", "wait")
            if intent_type_str not in ("greet", "ask", "share", "invite", "flee", "wait", "change_topic"):
                intent_type_str = "wait"
            emotion_str = data.get("emotion", "neutral")
            if emotion_str not in ("warm", "anxious", "curious", "neutral", "wary"):
                emotion_str = "neutral"

            intent = IntentMessage(
                tick=getattr(self._world, '_tick_id', 0) if self._world else 0,
                agent_id=speaker_id,
                intent_type=intent_type_str,
                target=data.get("target", listener_id),
                reasoning=data.get("reasoning", ""),
                urgency=float(data.get("urgency", 0.5)),
                emotion=emotion_str,
            )
            logger.info(f"[Intent] {speaker_name} → {intent.intent_type} ({intent.emotion}) | {intent.reasoning[:50]}...")
            return intent

        except Exception as e:
            logger.warning(f"[Intent] 意图生成失败 [{speaker_name}]: {e}")
            return IntentMessage(
                tick=getattr(self._world, '_tick_id', 0) if self._world else 0,
                agent_id=speaker_id,
                intent_type="wait",
                target=listener_id,
                reasoning="意图生成失败，保持沉默",
                urgency=0.5,
                emotion="neutral",
            )

    async def _generate_dialogue(
        self,
        speaker_id: str,
        speaker_name: str,
        listener_id: str,
        listener_name: str,
        speaker_agent: Any,
        override_speech: Optional[str] = None,
        intent: Optional[IntentMessage] = None,
    ) -> DialogueMessage:
        if override_speech:
            return DialogueMessage(
                from_agent=speaker_id,
                to_agent=listener_id,
                utterance=override_speech,
                emotion_tag=Emotion.NEUTRAL,
                intent_type=IntentType.SHARE,
            )

        recent_context = "\n".join([
            f"{self.agent_names.get(d.from_agent, d.from_agent)}: {d.utterance}"
            for d in self.conversation_log[-6:]
        ])

        # 获取角色背景信息
        speaker_info = ""
        if speaker_agent:
            if hasattr(speaker_agent, 'personality') and speaker_agent.personality:
                p = speaker_agent.personality
                if isinstance(p, dict):
                    speaker_info += f"性格特点：O={p.get('openness', 0.5)}, C={p.get('conscientiousness', 0.5)}, E={p.get('extraversion', 0.5)}, A={p.get('agreeableness', 0.5)}, N={p.get('neuroticism', 0.5)}\n"
                else:
                    speaker_info += f"性格特点：O={p.openness}, C={p.conscientiousness}, E={p.extraversion}, A={p.agreeableness}, N={p.neuroticism}\n"
            if hasattr(speaker_agent, 'identity_tags') and speaker_agent.identity_tags:
                speaker_info += f"身份标签：{speaker_agent.identity_tags.get('primary', '')}\n"
            if hasattr(speaker_agent, 'mood') and speaker_agent.mood:
                speaker_info += f"当前心情：{speaker_agent.mood}\n"

        # ADR-001: 基于意图类型构建引导提示
        intent_guidance = ""
        if intent:
            intent_emotion_map = {
                "warm": "温暖、友好地",
                "anxious": "有些担忧地",
                "curious": "好奇地",
                "neutral": "平淡地",
                "wary": "警惕地",
            }
            emotion_hint = intent_emotion_map.get(intent.emotion, "自然地")
            intent_guidance = f"你的当前意图是【{intent.intent_type}】，请以【{emotion_hint}】的语气回应。"

        prompt = f"""你是 {speaker_name}，正在和 {listener_name} 自然地交谈。

{speaker_info}
当前对话：
{recent_context}

{intent_guidance}
请生成 {speaker_name} 的回复，要自然、符合角色性格，30-50字：
"""

        try:
            llm = self._get_llm_for_purpose("dialogue_generation")
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=150,
            )
            utterance = response.strip()

            think_match = re.search(r'\[THINK\](.*?)\[/THINK\]', utterance, re.DOTALL)
            if think_match:
                think_content = think_match.group(1).strip()
                logger.debug(f"[Dialogue] {speaker_name} THINK: {think_content}")

            utterance = re.sub(r'\[THINK\].*?\[/THINK\]', '', utterance, flags=re.DOTALL)
            utterance = re.sub(r'\[/?SPEAK\]', '', utterance, flags=re.IGNORECASE)
            utterance = utterance.replace('"', '').replace('"', '').replace('"', '').strip()

            parts = utterance.split('\n')
            cleaned_parts = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if any(keyword in part for keyword in [
                    'The user', 'user says', 'play as', '扮演',
                    '回复', '对话', 'characters', '需要', '考虑',
                    'should respond', 'natural', '简短', '以内',
                ]):
                    continue
                if part.startswith(('- ', '1.', '2.', '3.', '4.', '5.')):
                    continue
                if len(part) >= 2:
                    cleaned_parts.append(part)

            utterance = ' '.join(cleaned_parts).strip()

            if not utterance or len(utterance.strip()) < 2:
                utterance = f"（{speaker_name}沉默了一下）"

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            utterance = f"（{speaker_name}沉默了一下）"

        return DialogueMessage(
            from_agent=speaker_id,
            to_agent=listener_id,
            utterance=utterance,
            emotion_tag=Emotion.NEUTRAL,
            intent_type=IntentType.SHARE,
            micro_action=self._maybe_generate_micro_action(speaker_agent, dialogue),
        )

    def _maybe_generate_micro_action(self, speaker_agent, dialogue) -> Optional[str]:
        """
        V0.7: 根据条件生成微观动作
        - 优先使用 SubconsciousEngine（角色自定义潜意识规则）
        - 回退到随机动作库
        - 情绪高唤醒时概率更高
        """
        import random

        # 基础概率 15%
        probability = 0.15

        # 如果 speaker_agent 有 emotion_model，检查唤醒度
        arousal = 0.5
        if speaker_agent and hasattr(speaker_agent, 'emotion_model'):
            arousal = speaker_agent.emotion_model.arousal
            if arousal > 0.6:
                probability += 0.2  # 高唤醒+20%

        if random.random() > probability:
            return None

        # V0.7: 优先使用 SubconsciousEngine
        if speaker_agent and hasattr(speaker_agent, 'subconscious_engine'):
            world_snapshot = {
                "location": getattr(speaker_agent, '_current_location', ''),
                "visible_objects": [],
                "nearby_agents": [],
                "time_of_day": "",
            }
            micro_action = speaker_agent.subconscious_engine.get_micro_action_for_dialogue(
                speaker_agent, world_snapshot, emotion_arousal=arousal
            )
            if micro_action:
                return micro_action

        # 回退到随机动作库
        micro_actions = [
            "轻轻抿了口茶",
            "若有所思地点头",
            "目光在对方脸上停留了一瞬",
            "手指无意识地敲着桌面",
            "微微皱起眉头",
            "露出不易察觉的微笑",
            "身体微微前倾",
            "手指轻轻捻着衣角",
            "眼神飘向窗外",
            "轻叹一口气",
        ]

        return random.choice(micro_actions)

    def _speaker_agent(self, agent_id: str):
        if self._world and self._world._agent_registry:
            return self._world._agent_registry.get(agent_id)
        return None


class DialogueManager:
    """
    对话管理器 - 管理所有对话会话
    V0.5: 集成记忆归档触发
    """

    def __init__(self, llm, world, archiver=None, retriever=None, router=None):
        self._llm = llm
        self._world = world
        self._sessions: dict[tuple[str, str], DialogueSession] = {}
        self._active_agents: set[str] = set()
        self._subscribers: list = []
        self._archiver = archiver
        self._retriever = retriever
        self._router = router

    async def trigger_dialogue(self, agent_a_id: str, agent_b_id: str, agent_registry: dict[str, Any]) -> None:
        pair = tuple(sorted([agent_a_id, agent_b_id]))
        if pair in self._sessions:
            return

        agent_names = self._world.agent_names

        session = DialogueSession(
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            agent_names=agent_names,
            llm=self._llm,
            world=self._world,
            archiver=self._archiver,
            retriever=self._retriever,
            router=self._router,
        )

        self._sessions[pair] = session
        self._active_agents.add(agent_a_id)
        self._active_agents.add(agent_b_id)

        asyncio.create_task(self._run_session(session))

    async def _run_session(self, session: DialogueSession) -> None:
        try:
            result = await session.run()
            logger.info(f"[Dialogue] 会话结束: {result}")
        except Exception as e:
            logger.error(f"对话会话异常: {e}")
        finally:
            self._active_agents.discard(session.agent_a)
            self._active_agents.discard(session.agent_b)
            pair = tuple(sorted([session.agent_a, session.agent_b]))
            self._sessions.pop(pair, None)

    def is_agent_active(self, agent_id: str) -> bool:
        return agent_id in self._active_agents

    async def interrupt_dialogue(self, agent_id: str) -> None:
        """中断指定角色的对话会话"""
        self._active_agents.discard(agent_id)
        # 停止该角色参与的所有会话
        for pair, session in list(self._sessions.items()):
            if agent_id in (session.agent_a, session.agent_b):
                session.stop()
                self._sessions.pop(pair, None)

    def set_relationships(self, relationships: list) -> None:
        """V0.4 兼容：存储关系数据（当前 V0.5 版本中关系由 Relationship 类管理）"""
        self._relationships = relationships

    def broadcast_state(self) -> None:
        for subscriber in self._subscribers:
            try:
                subscriber({
                    "active_agents": list(self._active_agents),
                    "sessions": len(self._sessions),
                })
            except Exception as e:
                logger.error(f"广播失败: {e}")

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)