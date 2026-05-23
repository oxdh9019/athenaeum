"""
character_schema.py — V0.7 角色数据模型
扩展 Soul 层：InnerConflict、SubconsciousRule
"""

from pydantic import BaseModel, Field
from typing import Optional


class InnerConflict(BaseModel):
    """
    内在矛盾
    角色内心深处两个相互冲突的欲望或价值观
    """
    pole_a: str = Field(description="矛盾的第一极，如'渴望知识的自由传播'")
    pole_b: str = Field(description="矛盾的第二极，如'害怕古籍被不当使用而损毁'")
    description: str = Field(description="矛盾的具体描述，如'艾琳常常在借出珍本与保护古籍之间挣扎'")


class SubconsciousRule(BaseModel):
    """
    潜意识规则
    触发时自动产生的下意识动作，不经过思考
    """
    trigger: str = Field(description="触发词或场景描述，如'看到甜食'")
    action: str = Field(description="自动行为，如'目光多停留几秒，可能微笑'")
    priority: float = Field(default=0.2, description="触发概率权重 0.0-1.0")


class SoulConfig(BaseModel):
    """
    Soul 配置 - V0.7 核心
    包含驱动角色内在生命力的所有配置
    """
    core_desires: list = Field(default_factory=list, description="核心欲望列表")
    inner_conflict: Optional[InnerConflict] = Field(default=None, description="内在矛盾")
    subconscious_rules: list[SubconsciousRule] = Field(default_factory=list, description="潜意识规则列表")
    behavioral_tendencies: dict = Field(default_factory=dict, description="行为倾向")
    long_term_goals: list = Field(default_factory=list, description="长期目标")


class CharacterSchema(BaseModel):
    """
    完整角色数据模型
    """
    id: str
    name: str
    age: int = 0
    occupation: str = ""
    personality: dict = Field(default_factory=dict)
    identity_tags: dict = Field(default_factory=dict)
    backstory: str = ""
    initial_location: str = ""

    # V0.7 Soul 层
    soul: Optional[SoulConfig] = None

    # V0.5 记忆系统
    memory_settings: dict = Field(default_factory=dict)

    # V0.4 关系
    relationships: list = Field(default_factory=list)


def create_default_soul() -> SoulConfig:
    """创建默认 Soul 配置"""
    return SoulConfig(
        core_desires=[],
        inner_conflict=None,
        subconscious_rules=[],
        behavioral_tendencies={},
        long_term_goals=[],
    )