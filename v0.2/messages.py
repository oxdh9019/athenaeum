"""
messages.py — ADR-002 消息契约定义
IntentMessage / DialogueMessage / SystemMessage
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    GREET = "greet"
    ASK = "ask"
    SHARE = "share"
    INVITE = "invite"
    FLEE = "flee"
    WAIT = "wait"
    CHANGE_TOPIC = "change_topic"


class Emotion(str, Enum):
    WARM = "warm"
    ANXIOUS = "anxious"
    CURIOUS = "curious"
    NEUTRAL = "neutral"
    WARY = "wary"


class IntentMessage(BaseModel):
    """
    ADR-002: Agent 意图消息
    """
    id: str = Field(default_factory=lambda: f"intent_{uuid.uuid4().hex[:8]}")
    tick: int
    agent_id: str
    intent_type: IntentType
    target: Optional[str] = None          # 目标 Agent ID，或 None
    reasoning: str                        # 自然语言内部独白
    urgency: float = Field(ge=0.0, le=1.0)
    emotion: Emotion


class DialogueMessage(BaseModel):
    """
    ADR-002: Agent 间对话消息
    """
    id: str = Field(default_factory=lambda: f"dlg_{uuid.uuid4().hex[:8]}")
    tick: int
    from_agent: str
    to_agent: str
    utterance: str                        # 角色说出的自然语言
    emotion_tag: Emotion
    intent_ref: str                      # 关联的 IntentMessage ID


class SystemMessage(BaseModel):
    """
    系统级叙事注入消息
    """
    id: str = Field(default_factory=lambda: f"sys_{uuid.uuid4().hex[:8]}")
    tick: int
    type: str                            # e.g. "change_topic", "narrative_event"
    description: str
    affected_agents: list[str] = Field(default_factory=list)
    content: Optional[str] = None        # 注入的具体内容
