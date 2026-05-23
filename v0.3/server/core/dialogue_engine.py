"""
dialogue_engine.py — V0.3 对话引擎
双Agent交替对话，支持用户附身
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


RELATIONSHIP_DELTA = {
    (IntentType.SHARE, Emotion.WARM): 0.05,
    (IntentType.SHARE, Emotion.CURIOUS): 0.03,
    (IntentType.GREET, Emotion.WARM): 0.02,
    (IntentType.ASK, Emotion.CURIOUS): 0.02,
    (IntentType.INVITE, Emotion.WARM): 0.04,
    (IntentType.FLEE, Emotion.WARY): -0.08,
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
    """

    def __init__(
        self,
        agent_a_id: str,
        agent_b_id: str,
        agent_names: dict[str, str],
        llm,
        world=None,
        max_turns: int = 8,
        relationship_type: str = "stranger",
        shared_history: str = "",
        potential_conflicts: list[str] = None,
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

        # 关系数据（用于对话调制）
        self.relationship_type = relationship_type
        self.shared_history = shared_history
        self.potential_conflicts = potential_conflicts or []

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

    async def _do_turn(self) -> None:
        speaker_id = self._next_speaker
        listener_id = self.agent_b if speaker_id == self.agent_a else self.agent_a

        speaker_name = self.agent_names.get(speaker_id, speaker_id)
        listener_name = self.agent_names.get(listener_id, listener_id)

        speaker_agent = self._speaker_agent(speaker_id)
        if not speaker_agent:
            return

        override_speech = None
        override_intent = None
        if self._possess_event.is_set() and self._possessed_id == speaker_id:
            self._possess_event.clear()
            override_speech = self._possess_msg
            self._possessed_id = None
            self._possess_msg = None

        # 步骤1：生成结构化意图（ADR-001 两步架构）
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

        # 步骤2：基于意图生成对话
        dialogue = await self._generate_dialogue(
            speaker_id, speaker_name, listener_id, listener_name,
            speaker_agent, override_speech, intent
        )

        self.conversation_log.append(dialogue)

        # 检测重复内容，提前终止
        if self._turn_count > 3:
            recent = [d.utterance for d in self.conversation_log[-4:]]
            if self._detect_repetition(recent):
                logger.info(f"[Dialogue] 检测到重复内容，提前终止会话")
                self._running = False
                return

        if speaker_id == self.agent_a:
            await self._queue_a.put(dialogue)
        else:
            await self._queue_b.put(dialogue)

        # 步骤3：基于意图类型 + emotion 演化关系值
        delta = self.relationship.evolve(intent_type, emotion_tag)
        logger.info(f"[Dialogue] {speaker_name}: {dialogue.utterance[:50]}... | {intent_type} | Δ={delta:+.2f}")

        # 记录到世界状态，供前端展示
        if self._world:
            tick = self._world._tick_id if hasattr(self._world, '_tick_id') else 0
            await self._world.add_dialogue({
                "from": speaker_name,
                "from_id": speaker_id,
                "to": listener_name,
                "utterance": dialogue.utterance,
                "tick": tick,
            })

        self._next_speaker = listener_id

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
        # 获取环境上下文
        env_context = self._build_env_context(speaker_id)

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
                tags = speaker_agent.identity_tags
                primary = tags.get('primary', '') if isinstance(tags, dict) else ''
                speaker_info += f"身份标签：{primary}\n"
                # 官员语言风格引导
                if any(kw in primary for kw in ['官员', '政府', '噶厦', '工委']):
                    speaker_info += "注意：作为政府官员，语言应正式、含蓄，尊重等级制度。\n"
            if hasattr(speaker_agent, 'mood') and speaker_agent.mood:
                speaker_info += f"当前心情：{speaker_agent.mood}\n"

        # 关系调制
        relationship_modulation = ""
        if self.relationship_type and self.relationship_type != "stranger":
            relationship_modulation += f"关系类型：{self.relationship_type}\n"
        if self.potential_conflicts:
            conflict_str = '；'.join(self.potential_conflicts[:2])
            relationship_modulation += f"注意：双方存在立场冲突（{conflict_str}），对话应体现这种张力。\n"

        # 共同历史
        shared_history_section = ""
        if self.shared_history:
            shared_history_section = f"## 共同历史\n你们之间有以下的共同经历：{self.shared_history}\n"

        recent_context = "\n".join([
            f"{self.agent_names.get(d.from_agent, d.from_agent)}: {d.utterance}"
            for d in self.conversation_log[-6:]
        ]) if self.conversation_log else "（暂无历史对话）"

        prompt = f"""你是 {speaker_name}（ID: {speaker_id}），正在和 {listener_name} 交谈。

## 身份信息
{speaker_info}

## 环境上下文
{env_context}

## 关系与历史
{relationship_modulation}
{shared_history_section}

## 当前对话历史
{recent_context}

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
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )

            # 解析 JSON 意图
            text = response.strip()
            # 尝试提取 JSON
            import json
            try:
                # 直接解析
                data = json.loads(text)
            except json.JSONDecodeError:
                # 尝试从代码块中提取
                import re
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    raise ValueError("无法解析意图JSON")

            # 验证并构建 IntentMessage
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

    def _speaker_agent(self, agent_id: str):
        if self._world and self._world._agent_registry:
            return self._world._agent_registry.get(agent_id)
        return None

    def _build_env_context(self, speaker_id: str) -> str:
        """构建环境上下文信息"""
        if not self._world:
            return ""
        ctx = ""
        # 地点信息
        if hasattr(self._world, '_space'):
            loc_id = self._world._space._agent_locations.get(speaker_id)
            if loc_id:
                loc = self._world._locations.get(loc_id)
                if loc:
                    tags = ','.join(loc.tags) if loc.tags else ''
                    ctx += f"地点：{loc.name}"
                    if tags:
                        ctx += f"（{tags}）"
                    ctx += "\n"
        # 时间和天气
        if hasattr(self._world, '_time_of_day'):
            ctx += f"时间：{self._world._time_of_day.value}\n"
        if hasattr(self._world, '_weather'):
            ctx += f"天气：{self._world._weather.value}\n"
        # 环境音
        if hasattr(self._world, '_atmosphere') and self._world._atmosphere:
            ambient = self._world._atmosphere.get('ambient_sounds', [])
            if ambient:
                ctx += f"环境音：{','.join(ambient)}\n"
        return ctx

    def _detect_repetition(self, utterances: list[str]) -> bool:
        """检测重复内容（n-gram 重叠率超过60%则判定为重复）"""
        if len(utterances) < 3:
            return False
        def get_ngrams(text, n=3):
            chars = list(text.replace(" ", "").replace("\n", ""))[:30]
            return set(["".join(chars[i:i+n]) for i in range(len(chars)-n+1)]) if len(chars) >= n else set()
        sets = [get_ngrams(u) for u in utterances]
        for i in range(len(sets) - 1):
            if not sets[i] or not sets[i+1]:
                continue
            overlap = len(sets[i] & sets[i+1])
            if overlap > len(sets[i]) * 0.6:
                return True
        return False

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

        # 获取环境上下文
        env_context = self._build_env_context(speaker_id)

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
                tags = speaker_agent.identity_tags
                primary = tags.get('primary', '') if isinstance(tags, dict) else ''
                speaker_info += f"身份标签：{primary}\n"
                # 官员语言风格引导
                if any(kw in primary for kw in ['官员', '政府', '噶厦', '工委']):
                    speaker_info += "注意：作为政府官员，语言应正式、含蓄，尊重等级制度。\n"
            if hasattr(speaker_agent, 'mood') and speaker_agent.mood:
                speaker_info += f"当前心情：{speaker_agent.mood}\n"

        # 关系调制
        relationship_style = ""
        if self.relationship_type and self.relationship_type != "stranger":
            if self.relationship_type in ("公务往来", "official_business"):
                relationship_style = "注意：双方是公务往来关系，语言应正式、谨慎，避免私人话题。\n"
            elif self.relationship_type in ("商业庇护", "commercial_shelter"):
                relationship_style = "注意：存在商业庇护关系，一方可能有求于另一方，对话应体现这种权力动态。\n"
            elif self.relationship_type in ("邻居", "neighbor"):
                relationship_style = "注意：邻里关系，可以聊日常事务，语气轻松自然。\n"
            elif self.relationship_type in ("朋友", "friend"):
                relationship_style = "注意：朋友关系，可以分享私人想法和感受，语气亲切。\n"
        if self.potential_conflicts:
            conflict_str = '；'.join(self.potential_conflicts[:2])
            relationship_style += f"注意：双方存在立场冲突（{conflict_str}），对话应体现这种张力。\n"

        # 共同历史提醒
        shared_history_section = ""
        if self.shared_history:
            shared_history_section = f"共同历史：{self.shared_history}\n"

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

## 环境上下文
{env_context}

## 关系与历史
{relationship_style}{shared_history_section}

当前对话：
{recent_context}

{intent_guidance}
请生成 {speaker_name} 的回复，要自然、符合角色性格，30-50字：
"""

        try:
            response = await self._llm.chat(
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
            utterance = utterance.replace('[/SPEAK]', '').strip()
            utterance = utterance.replace('[SPEAK]', '').strip()
            
            utterance = re.sub(r'\[THINK\].*?\[/THINK\]', '', utterance, flags=re.DOTALL)
            
            utterance = utterance.replace('[/SPEAK]', '').strip()
            utterance = utterance.replace('"', '').strip()
            utterance = utterance.replace('“', '').strip()
            utterance = utterance.replace('”', '').strip()
            
            parts = utterance.split('\n')
            cleaned_parts = []
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                if any(keyword in part for keyword in [
                    'The user', 'user says', 'play as', '扮演',
                    '回复', '对话', 'characters', 'characters.',
                    '需要', '考虑', '让我想', 'I need', 'we need',
                    'should respond', 'natural', '简短', '以内',
                    '当前', '现在', '可能', '选择', '角色',
                    'acting as', 'Continue the', '对话是', 'conversation',
                    'Since Maria', 'Since Alexander', 'Since baker',
                    '- Maria:', '- Baker:', '- Alexander:',
                    'the baker might:', '面包师可能',
                    'another approach', 'maybe offer'
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
        )


class DialogueManager:
    """
    对话管理器 - 管理所有对话会话
    """

    def __init__(self, llm, world):
        self._llm = llm
        self._world = world
        self._sessions: dict[tuple[str, str], DialogueSession] = {}
        self._active_agents: set[str] = set()
        self._subscribers: list = []
        self._relationships: dict[tuple[str, str], dict] = {}

    def set_relationships(self, relationships: list[dict]) -> None:
        """设置关系数据，供对话时查询"""
        self._relationships.clear()
        for rel in relationships:
            key = tuple(sorted([rel.get('from_id', ''), rel.get('to_id', '')]))
            self._relationships[key] = rel

    def get_relationship(self, agent_a: str, agent_b: str) -> dict:
        """获取两个 agent 之间的关系数据"""
        key = tuple(sorted([agent_a, agent_b]))
        return self._relationships.get(key, {})

    async def trigger_dialogue(
        self,
        agent_a_id: str,
        agent_b_id: str,
        agent_registry: dict[str, Any],
        relationship_data: dict = None,
    ) -> None:
        pair = tuple(sorted([agent_a_id, agent_b_id]))
        if pair in self._sessions:
            return

        # 如果没有传入 relationship_data，自动从存储的关系中查找
        if relationship_data is None:
            relationship_data = self.get_relationship(agent_a_id, agent_b_id)

        agent_names = self._world.agent_names

        # 提取关系数据
        rel_type = "stranger"
        shared_hist = ""
        conflicts = []
        if relationship_data:
            rel_type = relationship_data.get('relationship_type', 'stranger')
            shared_hist = relationship_data.get('shared_history', '')
            conflicts = relationship_data.get('potential_conflicts', [])

        session = DialogueSession(
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            agent_names=agent_names,
            llm=self._llm,
            world=self._world,
            relationship_type=rel_type,
            shared_history=shared_hist,
            potential_conflicts=conflicts,
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
        self._active_agents.discard(agent_id)

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
