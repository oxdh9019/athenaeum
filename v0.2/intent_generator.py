"""
intent_generator.py — ADR-001 结构化意图生成器
输出 IntentMessage JSON
temperature=0.2（稳定、低随机）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from messages import IntentMessage, IntentType, Emotion
from needs import NeedQueue

logger = logging.getLogger(__name__)

INTENT_JSON_SCHEMA = """
请严格按以下 JSON Schema 输出意图，不要输出任何其他内容：

{
  "intent_type": "greet|ask|share|invite|flee|wait|change_topic",
  "target": "对方角色ID或null",
  "reasoning": "你的自然语言内部独白，描述为什么产生这个意图",
  "urgency": 0.0到1.0之间的浮点数，
  "emotion": "warm|anxious|curious|neutral|wary"
}
"""


class IntentGenerator:
    """
    结构化意图生成器 — ADR-001 正式版

    输入: 角色信息 + 当前需求队列 + 记忆上下文 + 最近对话
    输出: IntentMessage
    """

    def __init__(self, llm):
        self._llm = llm

    async def generate(
        self,
        agent_id: str,
        agent_name: str,
        personality_desc: str,
        needs: NeedQueue,
        memory_context: list[dict],
        recent_dialogue: list[dict],
        other_agent_name: str,
        other_agent_id: str,
        current_location: str = "翡翠城",
        override_intent: Optional[dict] = None,
    ) -> IntentMessage:
        """
        生成结构化意图。

        参数:
            override_intent: 可选，若传入则直接使用（用于用户附身注入）
        """
        if override_intent:
            return IntentMessage(
                tick=0,
                agent_id=agent_id,
                intent_type=IntentType(override_intent["intent_type"]),
                target=override_intent.get("target", other_agent_id),
                reasoning=override_intent.get("reasoning", "用户附身注入"),
                urgency=override_intent.get("urgency", 0.5),
                emotion=Emotion(override_intent.get("emotion", "neutral")),
            )

        system_prompt = self._build_system_prompt(
            agent_id, agent_name, personality_desc, needs, current_location
        )
        user_prompt = self._build_user_prompt(
            agent_name, memory_context, recent_dialogue, other_agent_name, other_agent_id
        )

        raw = await self._llm.chat(
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            temperature=0.2,
            json_mode=True,
        )

        intent = self._parse_intent(raw, agent_id)
        logger.info(f"[{agent_name}] 意图生成 → {intent.intent_type.value} | "
                    f"emotion={intent.emotion.value} | urgency={intent.urgency:.2f}")
        return intent

    def _build_system_prompt(
        self,
        agent_id: str,
        agent_name: str,
        personality_desc: str,
        needs: NeedQueue,
        current_location: str,
    ) -> str:
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[intent_generator] needs 参数: {needs}")
        logger.info(f"[intent_generator] needs 类型: {type(needs)}")
        
        if needs:
            logger.info(f"[intent_generator] needs 有 top_need 方法: {hasattr(needs, 'top_need')}")
            try:
                top = needs.top_need()
                logger.info(f"[intent_generator] top_need 结果: {top}")
                top_need_str = (
                    f"当前最强烈需求: {top.name}（{top.level:.2f}）"
                    if top else "所有需求均已满足"
                )
            except Exception as e:
                logger.error(f"[intent_generator] 调用 top_need 失败: {e}")
                top_need_str = "获取需求失败"
        else:
            top_need_str = "所有需求均已满足"

        needs_fragment = needs.as_prompt_fragment() if needs else "无需求信息"
        
        return f"""你是 {agent_name}（ID: {agent_id}），正在 {current_location}。

## 身份
你是一个有血有肉的角色，有自己的性格、欲望和需求。

## 性格描述
{personality_desc}

## 当前需求状态
{needs_fragment}

{top_need_str}"""

## 输出要求
{INTENT_JSON_SCHEMA}

意图类型说明:
- greet: 打招呼、开启对话
- ask: 向对方提问、寻求信息
- share: 分享自己的经历、想法或感受
- invite: 邀请对方参与某事
- flee: 回避、退出现有对话
- wait: 保持沉默或观察
- change_topic: 主动转换话题，打破僵局

请根据当前需求状态和对话上下文，选择最合适的意图类型。"""

    def _build_user_prompt(
        self,
        agent_name: str,
        memory_context: list[dict],
        recent_dialogue: list[dict],
        other_agent_name: str,
        other_agent_id: str,
    ) -> str:
        memory_lines = "\n".join(
            f"- {m['role']}: {m['content']}" for m in memory_context[-10:]
        )
        dialogue_lines = "\n".join(
            f"- {d['from']} 对 {d['to']}: {d['utterance']}"
            for d in recent_dialogue[-6:]
        ) if recent_dialogue else "（暂无历史对话）"

        return f"""## 我与 {other_agent_name} 的对话历史
{dialogue_lines}

## 我的记忆上下文
{memory_lines}

## 当前情境
{other_agent_name}（{other_agent_id}）就在我面前。我应该如何行动？

请输出 JSON 格式的意图。"""

    def _parse_intent(self, raw: str, agent_id: str) -> IntentMessage:
        """解析 LLM 返回的 JSON 意图"""
        # 策略1: 尝试直接解析整段文本
        text = raw.strip()

        # 策略2: 提取 ```json ... ``` 代码块
        code_block_match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
        if code_block_match:
            text = code_block_match.group(1).strip()

        # 策略3: 找最外层 JSON 对象（支持嵌套）
        if not self._is_valid_intent_json(text):
            brace_match = re.search(r'(\{.*\})', raw, re.DOTALL)
            if brace_match:
                text = brace_match.group(1).strip()

        try:
            data = json.loads(text)
            # 验证必需字段
            if "intent_type" not in data:
                raise ValueError("missing intent_type")
            return IntentMessage(
                tick=0,
                agent_id=agent_id,
                intent_type=IntentType(data["intent_type"]),
                target=data.get("target"),
                reasoning=data.get("reasoning", ""),
                urgency=float(data.get("urgency", 0.5)),
                emotion=Emotion(data.get("emotion", "neutral")),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"意图解析失败 ({e})，原始内容: {raw[:200]!r}")
            return IntentMessage(
                tick=0,
                agent_id=agent_id,
                intent_type=IntentType.WAIT,
                target=None,
                reasoning="意图解析失败，保持沉默",
                urgency=0.5,
                emotion=Emotion.NEUTRAL,
            )

    def _is_valid_intent_json(self, text: str) -> bool:
        """检查文本是否为有效的意图 JSON"""
        try:
            data = json.loads(text)
            return isinstance(data, dict) and "intent_type" in data
        except Exception:
            return False
