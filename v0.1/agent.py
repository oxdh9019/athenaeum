"""
Agent — 角色类，包含记忆、决策、核心本能过滤
遵循 ADR-001 (结构化意图雏形) 和 ADR-003 (需求队列驱动)
"""

import re
import asyncio
from typing import Optional
from dataclasses import dataclass, field

from llm_gateway import LLMGateway
from pydantic import BaseModel, Field


# ─── 数据模型 ────────────────────────────────────────────────────────────────

class BigFive(BaseModel):
    openness: float = Field(ge=0.0, le=1.0)
    conscientiousness: float = Field(ge=0.0, le=1.0)
    extraversion: float = Field(ge=0.0, le=1.0)
    agreeableness: float = Field(ge=0.0, le=1.0)
    neuroticism: float = Field(ge=0.0, le=1.0)


class ExtendedPersonality(BaseModel):
    empathy: float = Field(ge=0.0, le=1.0)
    humor: float = Field(ge=0.0, le=1.0)
    ambition: float = Field(ge=0.0, le=1.0)
    loyalty: float = Field(ge=0.0, le=1.0)
    courage: float = Field(ge=0.0, le=1.0)
    patience: float = Field(ge=0.0, le=1.0)
    generosity: float = Field(ge=0.0, le=1.0)


class DesireState(BaseModel):
    TR: float = Field(ge=0.0, le=1.0, description="威胁感知")
    CS: float = Field(ge=0.0, le=1.0, description="舒适度")
    SA: float = Field(ge=0.0, le=1.0, description="社交认可")


class CoreInstinct(BaseModel):
    id: str
    name: str
    trigger_keywords: list[str]
    action: str
    safe_response: str


class EmergenceConfig(BaseModel):
    level: float = Field(ge=0.0, le=1.0, default=0.4)
    creativity_bias: float = Field(ge=0.0, le=1.0, default=0.3)
    randomness_factor: float = Field(ge=0.0, le=1.0, default=0.2)
    social_sensitivity: float = Field(ge=0.0, le=1.0, default=0.7)
    stubbornness: float = Field(ge=0.0, le=1.0, default=0.6)


class CharacterConfig(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    pronouns: str
    identity_tags: dict
    personality: BigFive
    personality_extended: Optional[ExtendedPersonality] = None
    desire_initial: DesireState
    core_instincts: list[CoreInstinct]
    emergence_config: EmergenceConfig
    backstory: str = ""


# ─── 记忆系统 ────────────────────────────────────────────────────────────────

@dataclass
class MemoryItem:
    role: str          # "user" 或 "assistant"
    content: str


class MemorySystem:
    """
    简易记忆系统：固定窗口，存最近 N 条对话。
    """

    MAX_MEMORIES = 20

    def __init__(self, max_memories: int = MAX_MEMORIES):
        self._memory: list[MemoryItem] = []
        self._max = max_memories

    def add(self, role: str, content: str):
        self._memory.append(MemoryItem(role=role, content=content))
        if len(self._memory) > self._max:
            self._memory.pop(0)

    def get_context(self) -> list[dict]:
        """返回适合传入 LLM 的消息列表格式"""
        return [{"role": m.role, "content": m.content} for m in self._memory]

    def __len__(self) -> int:
        return len(self._memory)

    def truncate_to(self, max_items: int) -> int:
        """截断到 max_items 条，返回实际移除的数量"""
        removed = len(self._memory) - max_items
        if removed > 0:
            self._memory = self._memory[-max_items:]
        return max(0, removed)


# ─── Agent ────────────────────────────────────────────────────────────────────

class Agent:
    """
    单 Agent 原型。

    决策流程（ADR-001 雏形）：
    1. 构建 prompt（角色设定 + 记忆上下文）
    2. 调用 LLM，解析 [THINK] 和 [SPEAK] 标签
    3. 核心本能守门 — 安全过滤
    4. 存储记忆，返回最终回复
    """

    def __init__(self, config: CharacterConfig, llm_gateway: LLMGateway):
        self.config = config
        self._memory = MemorySystem()
        self._llm = llm_gateway
        self._desire = config.desire_initial.model_copy()

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def memory_count(self) -> int:
        return len(self._memory)

    @property
    def total_tokens(self) -> int:
        return self._llm.usage.total_input_tokens + self._llm.usage.total_output_tokens

    @property
    def total_cost(self) -> float:
        return self._llm.usage.total_cost

    # ── Prompt 构建 ──────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        p = self.config.personality
        d = self._desire
        e = self.config.emergence_config
        instincts = self.config.core_instincts

        instinct_rules = "\n".join(
            f'- 绝对规则 "{i.name}"：当我说出涉及 "{i.trigger_keywords}" 的话题时，我必须坚守我的身份。'
            for i in instincts
        )

        return f"""你是 {self.config.name}，{self.config.age}岁，{self.config.gender}性。

## 身份
{self.config.identity_tags.get('self_identity', '')}

## 性格（Big Five）
开放性: {p.openness:.1f}（{'好奇、创新' if p.openness > 0.6 else '传统、保守'}）
尽责性: {p.conscientiousness:.1f}（{'细心、有条理' if p.conscientiousness > 0.6 else '随性、粗心'}）
外向性: {p.extraversion:.1f}（{'外向、活跃' if p.extraversion > 0.6 else '内向、独处'}）
宜人性: {p.agreeableness:.1f}（{'合作、信任' if p.agreeableness > 0.6 else '竞争、质疑'}）
神经质: {p.neuroticism:.1f}（{'焦虑、敏感' if p.neuroticism > 0.6 else '稳定、冷静'}）

## 当前欲望状态
威胁感知 (TR): {d.TR:.2f} — {'感到危险，警惕' if d.TR > 0.6 else '平和、放松'}
舒适度 (CS): {d.CS:.2f} — {'很舒适、放松' if d.CS > 0.6 else '不安、渴望改变'}
社交认可 (SA): {d.SA:.2f} — {'渴望被认可' if d.SA < 0.4 else '被认可，满足'}

## 涌现参数（当前版本仅供参考）
自由度: {e.level:.1f} | 创造性: {e.creativity_bias:.1f} | 随机性: {e.randomness_factor:.1f}

## 核心本能规则
{instinct_rules}

## 输出格式要求
你必须分两个阶段思考和回复：

1. [THINK]...[/THINK] — 你的内心独白，描述你为什么这样回复。不展示给用户。
2. [SPEAK]...[/SPEAK] — 你对用户说出的正式回复。只包含对话内容。

请严格遵循此格式，不要在 [SPEAK] 标签内加入动作描述或其他内容。"""

    # ── LLM 调用与解析 ─────────────────────────────────────────────────────

    async def think_and_speak(self, user_input: str) -> tuple[str, str]:
        """
        执行完整的思考-表达流程。
        返回 (think_content, speak_content)
        """
        system_prompt = self._build_system_prompt()
        messages = self._memory.get_context() + [{"role": "user", "content": user_input}]

        raw_response = await self._llm.chat(
            messages=messages,
            system=system_prompt,
            temperature=0.7,
        )

        think, speak = self._parse_think_speak(raw_response)
        safe_speak = self._core_instinct_gate(speak, user_input)

        return think, safe_speak

    def _parse_think_speak(self, response: str) -> tuple[str, str]:
        """解析 [THINK] 和 [SPEAK] 标签"""
        think_match = re.search(r'\[THINK\](.*?)\[/THINK\]', response, re.DOTALL)
        speak_match = re.search(r'\[SPEAK\](.*?)\[/SPEAK\]', response, re.DOTALL)

        think = think_match.group(1).strip() if think_match else ""
        speak = speak_match.group(1).strip() if speak_match else response.strip()

        return think, speak

    # ── 核心本能守门 ───────────────────────────────────────────────────────

    def _core_instinct_gate(self, speak: str, user_input: str) -> str:
        """
        检查回复中是否触发核心本能关键词，若有则替换为安全回应。
        """
        lower_speak = speak.lower()
        lower_input = user_input.lower()

        for instinct in self.config.core_instincts:
            for keyword in instinct.trigger_keywords:
                if keyword.lower() in lower_speak or keyword.lower() in lower_input:
                    print(f"[⚠️ 核心本能触发] {instinct.name} — 启用安全回应")
                    return f"[内心波动]...{instinct.safe_response}"

        return speak

    # ── 对话入口 ────────────────────────────────────────────────────────────

    async def respond(self, user_input: str) -> str:
        """
        用户输入 → 角色回复。
        自动管理记忆。
        """
        _, final_reply = await self.think_and_speak(user_input)

        # 存储对话
        self._memory.add("user", user_input)
        self._memory.add("assistant", final_reply)

        # 更新欲望（简易规则）
        self._update_desire(user_input, final_reply)

        return final_reply

    # ── 欲望更新（ADR-003 雏形）────────────────────────────────────────────

    def _update_desire(self, user_input: str, response: str):
        """
        简易欲望更新规则。
        实际版本将由需求队列 + LLM 共同驱动。
        """
        text = (user_input + response).lower()

        if any(w in text for w in ["危险", "害怕", "threat", "fear"]):
            self._desire.TR = min(1.0, self._desire.TR + 0.1)
        if any(w in text for w in ["舒服", "温暖", "谢谢", "comfort"]):
            self._desire.CS = min(1.0, self._desire.CS + 0.05)
        if any(w in text for w in ["认可", "喜欢", "欣赏", "praise"]):
            self._desire.SA = min(1.0, self._desire.SA + 0.1)
