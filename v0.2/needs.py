"""
needs.py — ADR-003 需求队列系统基础版
Safety / Belonging / Novelty 三个核心需求
"""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


@dataclass
class Need:
    """单个需求"""
    name: str                    # safety | belonging | novelty
    level: float = 0.5           # 0.0 (完全满足) ~ 1.0 (极度渴望)
    target: Optional[str] = None  # 社交需求目标（角色ID）

    def is_active(self, threshold: float = 0.6) -> bool:
        """需求是否强烈到应该影响决策"""
        return self.level >= threshold

    def satisfy(self, delta: float):
        """满足需求，减少渴望度"""
        self.level = max(0.0, self.level - delta)

    def increase(self, delta: float):
        """需求未满足，增加渴望度"""
        self.level = min(1.0, self.level + delta)


class NeedQueue:
    """
    需求队列 — ADR-003

    每次决策前根据环境、记忆更新需求度。
    需求度高的项目优先影响意图生成。
    """

    def __init__(self):
        self._needs: dict[str, Need] = {
            "safety": Need(name="safety", level=0.2),
            "belonging": Need(name="belonging", level=0.4),
            "novelty": Need(name="novelty", level=0.5),
        }

    def get(self, name: str) -> Need:
        return self._needs[name]

    def active_needs(self) -> list[Need]:
        """返回当前活跃（level >= 0.6）的需求列表"""
        return [n for n in self._needs.values() if n.is_active()]

    def top_need(self) -> Optional[Need]:
        """返回当前最强烈的需求"""
        active = self.active_needs()
        if not active:
            return max(self._needs.values(), key=lambda n: n.level)
        return max(active, key=lambda n: n.level)

    def update_from_environment(self, event_text: str):
        """根据环境事件更新需求"""
        text = event_text.lower()

        # 危险事件 → safety 上升
        if any(k in text for k in ["危险", "害怕", "threat", "fear", "storm", "冲突"]):
            self._needs["safety"].increase(0.15)

        # 孤独感 → belonging 上升
        if any(k in text for k in ["一个人", "孤独", "没人", "alone"]):
            self._needs["belonging"].increase(0.1)

        # 重复事件 → novelty 上升
        if any(k in text for k in ["一样", "重复", "无聊", "same"]):
            self._needs["novelty"].increase(0.1)

    def update_from_interaction(self, intent_type: str, emotion: str, positive: bool):
        """根据互动结果更新需求"""
        if positive:
            self._needs["belonging"].satisfy(0.08)
        else:
            self._needs["belonging"].increase(0.05)

        if intent_type in ["ask", "share"]:
            self._needs["novelty"].satisfy(0.05)

    def as_prompt_fragment(self) -> str:
        """生成用于 Prompt 的需求描述"""
        lines = ["## 当前需求状态"]
        for name, need in self._needs.items():
            status = "渴望" if need.is_active() else "满足"
            target = f"（目标: {need.target}）" if need.target else ""
            lines.append(f"- {name}: {need.level:.2f} [{status}] {target}")
        return "\n".join(lines)
