"""
agent.py — V0.2 Agent 封装
扩展 V0.1 的 Agent，加入需求队列和 personality_desc
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from typing import Optional

_v01_path = Path(__file__).parent.parent / "v0.1"

_v01_spec = importlib.util.spec_from_file_location(
    "v01_agent", _v01_path / "agent.py"
)
_v01_module = importlib.util.module_from_spec(_v01_spec)

original_sys_path = sys.path.copy()
try:
    sys.path.insert(0, str(_v01_path))
    _v01_spec.loader.exec_module(_v01_module)
finally:
    sys.path = original_sys_path

_V01Agent = _v01_module.Agent
CharacterConfig = _v01_module.CharacterConfig
CoreInstinct = _v01_module.CoreInstinct
DesireState = _v01_module.DesireState

from needs import NeedQueue
from llm_gateway import LLMGateway


class V02Agent:
    """
    V0.2 Agent — 在 V0.1 Agent 基础上扩展

    新增:
    - needs: NeedQueue (ADR-003)
    - personality_desc: 用于 LLM prompt 的性格描述字符串
    """

    def __init__(
        self,
        config: CharacterConfig,
        llm: LLMGateway,
        needs_initial: Optional[dict] = None,
        max_memory: int = 20,
    ):
        self._agent = _V01Agent(config, llm)
        self._config = config
        self._needs = NeedQueue()
        if needs_initial:
            self._needs.get("safety").level = needs_initial.get("safety", 0.2)
            self._needs.get("belonging").level = needs_initial.get("belonging", 0.4)
            self._needs.get("novelty").level = needs_initial.get("novelty", 0.5)

        self._max_memory = max_memory

    @classmethod
    def from_yaml(cls, path: Path, llm: LLMGateway) -> "V02Agent":
        """从 YAML 文件加载角色配置"""
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        basic = data["basic_info"]
        psych = data["psychology"]["personality"]

        desire_data = data.get("desire_initial", {"TR": 0.5, "CS": 0.5, "SA": 0.5})
        desire_initial = DesireState(**desire_data)

        config = CharacterConfig(
            id=basic["id"],
            name=basic["name"],
            age=basic["age"],
            gender=basic["gender"],
            pronouns=basic["pronouns"],
            identity_tags=basic["identity_tags"],
            personality=psych["big_five"],
            personality_extended=psych.get("extended"),
            desire_initial=desire_initial,
            core_instincts=[CoreInstinct.parse_obj(i) for i in data["core_instincts"]["ABSOLUTE_PRIORITY"]],
            emergence_config=data.get("emergence_config", {}),
            backstory=data.get("backstory", ""),
        )

        return cls(
            config=config,
            llm=llm,
            needs_initial=data.get("needs_initial"),
        )

    @property
    def id(self) -> str:
        return self._config.id

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def needs(self) -> NeedQueue:
        return self._needs

    @property
    def personality_desc(self) -> str:
        """生成用于 LLM 的性格描述字符串"""
        p = self._config.personality
        ep = getattr(self._config, "personality_extended", None)

        lines = [
            f"开放性: {p.openness:.1f} — {'好奇、创新、追求新奇' if p.openness > 0.6 else '传统、保守、循规蹈矩'}",
            f"尽责性: {p.conscientiousness:.1f} — {'细心、有条理、尽职尽责' if p.conscientiousness > 0.6 else '随性、粗心、灵活'}",
            f"外向性: {p.extraversion:.1f} — {'外向、活跃、爱社交' if p.extraversion > 0.6 else '内向、独处、低调'}",
            f"宜人性: {p.agreeableness:.1f} — {'合作、信任、温和' if p.agreeableness > 0.6 else '竞争、质疑、强硬'}",
            f"神经质: {p.neuroticism:.1f} — {'焦虑、敏感、情绪化' if p.neuroticism > 0.6 else '稳定、冷静、自信'}",
        ]

        if ep:
            ep_dict = ep if isinstance(ep, dict) else ep.model_dump() if hasattr(ep, "model_dump") else {}
            for key, label in [
                ("empathy", "共情能力"), ("humor", "幽默感"),
                ("ambition", "野心"), ("loyalty", "忠诚"),
                ("courage", "勇气"), ("patience", "耐心"),
                ("generosity", "慷慨"),
            ]:
                val = ep_dict.get(key, 0.5)
                lines.append(f"{label}: {val:.1f}")

        return "\n".join(lines)

    @property
    def memory_context(self) -> list[dict]:
        """供对话引擎使用的记忆上下文"""
        return self._agent._memory.get_context()

    @property
    def total_tokens(self) -> int:
        return self._agent.total_tokens

    @property
    def total_cost(self) -> float:
        return self._agent.total_cost

    def add_memory(self, role: str, content: str):
        """手动添加记忆"""
        self._agent._memory.add(role, content)

    def truncate_memory(self, max_items: int):
        """截断记忆"""
        self._agent._memory.truncate_to(max_items)

    def __getattr__(self, name: str):
        """代理 V0.1 Agent 的属性"""
        return getattr(self._agent, name)