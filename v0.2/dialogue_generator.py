"""
dialogue_generator.py — 对话生成模块
基于 IntentMessage + 上下文生成自然语言回复
temperature=0.8（高创造性）
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from messages import IntentMessage, DialogueMessage, Emotion, IntentType

logger = logging.getLogger(__name__)


class DialogueGenerator:
    """
    对话生成器 — 基于结构化意图生成自然语言

    输入: IntentMessage + 角色设定 + 记忆
    输出: DialogueMessage
    """

    def __init__(self, llm):
        self._llm = llm

    async def generate(
        self,
        intent: IntentMessage,
        agent_id: str,
        agent_name: str,
        agent_personality_desc: str,
        relationship: float,
        memory_context: list[dict],
        other_agent_name: str,
        override_speech: Optional[str] = None,
    ) -> DialogueMessage:
        """
        基于意图生成对话。

        参数:
            override_speech: 可选，若传入则直接使用（用于用户附身注入）
        """
        if override_speech:
            utterance = override_speech
        else:
            utterance = await self._generate_speech(
                intent, agent_name, agent_personality_desc,
                relationship, memory_context, other_agent_name
            )

        dialogue = DialogueMessage(
            tick=intent.tick,
            from_agent=agent_id,
            to_agent=intent.target or "",
            utterance=utterance,
            emotion_tag=intent.emotion,
            intent_ref=intent.id,
        )

        logger.info(f"[{agent_name}] → [{other_agent_name}]: {utterance[:50]}...")
        return dialogue

    async def _generate_speech(
        self,
        intent: IntentMessage,
        agent_name: str,
        personality_desc: str,
        relationship: float,
        memory_context: list[dict],
        other_agent_name: str,
    ) -> str:
        system_prompt = self._build_system_prompt(
            agent_name, personality_desc, intent, relationship
        )
        user_prompt = self._build_user_prompt(
            agent_name, memory_context, intent, other_agent_name
        )

        raw = await self._llm.chat(
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            temperature=0.8,
        )

        return self._clean_speech(raw)

    def _build_system_prompt(
        self,
        agent_name: str,
        personality_desc: str,
        intent: IntentMessage,
        relationship: float,
    ) -> str:
        rel_desc = self._relationship_description(relationship)
        emotion_tone = self._emotion_tone(intent.emotion)

        intent_instruction = self._intent_to_instruction(intent.intent_type)

        return f"""你是 {agent_name}。

## 性格
{personality_desc}

## 当前关系
{rel_desc}

## 当前意图
- 类型: {intent.intent_type.value}
- 目标: {intent.target or "无特定目标"}
- 情绪: {intent.emotion.value}
- 内心独白: {intent.reasoning}

## 语气指导
{emotion_tone}

## 对话要求
{intent_instruction}

你只能输出角色说出的对话内容，不要加入动作描写（如 "*走进房间*"）。
回复长度: 1-3 句话。"""

    def _build_user_prompt(
        self,
        agent_name: str,
        memory_context: list[dict],
        intent: IntentMessage,
        other_agent_name: str,
    ) -> str:
        memory_lines = "\n".join(
            f"- {m['role']}: {m['content']}" for m in memory_context[-8:]
        ) or "（无记忆）"

        return f"""## 对话历史
{memory_lines}

## 情境
{agent_name} 想对 {other_agent_name} 说: {intent.reasoning}
请以 {agent_name} 的身份，说出符合当前意图的自然对话。"""

    def _clean_speech(self, raw: str) -> str:
        """去除 [THINK] 等标签，只保留对话"""
        text = re.sub(r'\[THINK\].*?\[/THINK\]', '', raw, flags=re.DOTALL)
        text = re.sub(r'\[SPEAK\](.*?)\[/SPEAK\]', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'\*.*?\*', '', text)  # 去除动作描写 *...*
        return text.strip()

    def _relationship_description(self, relationship: float) -> str:
        if relationship >= 0.8:
            return "挚友 — 彼此信任，无话不谈"
        elif relationship >= 0.5:
            return "好友 — 互相关心，关系融洽"
        elif relationship >= 0.2:
            return "熟人 — 点头之交，互相认识"
        elif relationship >= -0.2:
            return "陌生 — 关系中立"
        elif relationship >= -0.5:
            return "有矛盾 — 互相不满"
        else:
            return "敌对 — 互不信任"

    def _emotion_tone(self, emotion: Emotion) -> str:
        tones = {
            Emotion.WARM: "温和、友善、真诚",
            Emotion.ANXIOUS: "紧张、不安、小心翼翼",
            Emotion.CURIOUS: "好奇、期待、探索",
            Emotion.NEUTRAL: "平静、客观、适度",
            Emotion.WARY: "警惕、谨慎、有所保留",
        }
        return tones.get(emotion, "平静、自然")

    def _intent_to_instruction(self, intent_type: IntentType) -> str:
        instructions = {
            IntentType.GREET: "打招呼，开启对话，语气轻松友好。",
            IntentType.ASK: "提出问题，表达好奇或需求，口气委婉。",
            IntentType.SHARE: "主动分享经历或想法，口气真诚、敞开。",
            IntentType.INVITE: "发出邀请，语气热情有感染力。",
            IntentType.FLEE: "委婉退出对话，或转移话题，口气礼貌但疏离。",
            IntentType.WAIT: "保持沉默或简单应答，不主动展开。",
            IntentType.CHANGE_TOPIC: "主动提起新话题，打破当前节奏。",
        }
        return instructions.get(intent_type, "自然回应。")
