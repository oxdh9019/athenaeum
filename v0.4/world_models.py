"""
world_models.py — V0.4 世界工坊数据模型
Pydantic schemas for world, character, and relationship generation
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class LocationModel(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    capacity: int = 5


class WorldTimeRules(BaseModel):
    day_start_hour: int = 8
    day_end_hour: int = 22
    tick_interval_minutes: int = 60


class WorldAtmosphere(BaseModel):
    mood: str = "平和"
    dominant_themes: list[str] = Field(default_factory=list)
    ambient_sounds: list[str] = Field(default_factory=list)


class GeneratedWorld(BaseModel):
    name: str
    description: str
    locations: list[LocationModel] = Field(default_factory=list)
    time_rules: WorldTimeRules = Field(default_factory=WorldTimeRules)
    atmosphere: WorldAtmosphere = Field(default_factory=WorldAtmosphere)


class BigFivePersonality(BaseModel):
    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtendedPersonality(BaseModel):
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    humor: float = Field(default=0.5, ge=0.0, le=1.0)
    ambition: float = Field(default=0.5, ge=0.0, le=1.0)
    loyalty: float = Field(default=0.5, ge=0.0, le=1.0)
    courage: float = Field(default=0.5, ge=0.0, le=1.0)
    patience: float = Field(default=0.5, ge=0.0, le=1.0)
    generosity: float = Field(default=0.5, ge=0.0, le=1.0)


class NeedItem(BaseModel):
    name: str
    level: float = Field(default=0.5, ge=0.0, le=1.0)
    target: Optional[str] = None


class CharacterBackstory(BaseModel):
    title: str = ""
    childhood: str = ""
    adolescence: str = ""
    adulthood: str = ""
    present: str = ""
    turning_points: list = Field(default_factory=list)

    @field_validator('turning_points', mode='before')
    @classmethod
    def fix_turning_points(cls, v):
        if isinstance(v, str):
            return [{'description': v}]
        if isinstance(v, list):
            # Normalize each element
            result = []
            for item in v:
                if isinstance(item, dict):
                    result.append(item)
                elif isinstance(item, str):
                    result.append({'description': item})
                else:
                    result.append({'description': ''})
            return result
        return []


class CharacterIdentity(BaseModel):
    primary: str = ""
    secondary: list[str] = Field(default_factory=list)
    self_identity: str = ""


class CharacterAppearance(BaseModel):
    height: str = ""
    build: str = ""
    hair: str = ""
    eyes: str = ""
    face: str = ""
    distinguishing_features: list[str] = Field(default_factory=list)


class CharacterSocial(BaseModel):
    family: dict = Field(default_factory=dict)
    education: dict = Field(default_factory=dict)
    career: dict = Field(default_factory=dict)
    social_network: dict = Field(default_factory=dict)


class CharacterConfig(BaseModel):
    id: str
    name: str
    age: int = 30
    gender: str = "未知"
    pronouns: str = "他/她/它"

    appearance: CharacterAppearance = Field(default_factory=CharacterAppearance)
    identity_tags: CharacterIdentity = Field(default_factory=CharacterIdentity)
    social_background: CharacterSocial = Field(default_factory=CharacterSocial)

    personality: BigFivePersonality = Field(default_factory=BigFivePersonality)
    extended_personality: ExtendedPersonality = Field(default_factory=ExtendedPersonality)

    backstory: CharacterBackstory = Field(default_factory=CharacterBackstory)
    initial_location: str = ""

    # V0.4 新增字段
    needs: list[NeedItem] = Field(default_factory=list)
    introduce_text: Optional[str] = None  # 第一人称自我介绍（本地Qwen生成）

    @field_validator('pronouns', mode='before')
    @classmethod
    def fix_pronouns(cls, v):
        if isinstance(v, list):
            if len(v) >= 3:
                return f"{v[0]}/{v[1]}/{v[2]}"
            elif len(v) == 2:
                return f"{v[0]}/{v[1]}"
            elif len(v) == 1:
                return v[0]
            else:
                return "他/她/它"
        if isinstance(v, str):
            return v
        return "他/她/它"

    @field_validator('needs', mode='before')
    @classmethod
    def fix_needs(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            if not v:
                return []
            # 处理字符串列表 ["belonging", "safety"]
            if v and isinstance(v[0], str):
                return [{"name": n, "level": 0.5} for n in v]
            # 已经是 NeedItem 格式
            return v
        if isinstance(v, dict):
            # 处理 {"belonging": 0.6, "safety": 0.8} 格式
            return [{"name": k, "level": float(v)} for k, v in v.items()]
        return []

    @field_validator('identity_tags', mode='before')
    @classmethod
    def fix_identity_tags(cls, v):
        if isinstance(v, dict):
            # 确保 secondary 是列表
            if 'secondary' in v and isinstance(v['secondary'], str):
                v['secondary'] = [v['secondary']]
            return v
        if isinstance(v, str):
            # LLM 返回字符串而不是对象
            return {"primary": v, "secondary": [], "self_identity": ""}
        # 返回默认值
        return {"primary": "", "secondary": [], "self_identity": ""}

    @field_validator('appearance', mode='before')
    @classmethod
    def fix_appearance(cls, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            # LLM 返回字符串描述而不是对象
            return {"height": "", "build": "", "hair": "", "eyes": "", "face": v, "distinguishing_features": []}
        return {}

    @field_validator('social_background', mode='before')
    @classmethod
    def fix_social_background(cls, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            # LLM 返回字符串而不是对象
            return {"family": {}, "education": {}, "career": {}, "social_network": {}}
        return {}

    @field_validator('backstory', mode='before')
    @classmethod
    def fix_backstory(cls, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return {"title": "", "childhood": "", "adolescence": "", "adulthood": "", "present": v, "turning_points": []}
        return {}

    @field_validator('personality', mode='before')
    @classmethod
    def fix_personality(cls, v):
        if isinstance(v, dict):
            return v
        return {}


class CharacterPairRelationship(BaseModel):
    from_id: str
    to_id: str
    relationship_type: str  # friend, rival, family, neighbor, stranger, etc.
    strength: float = Field(default=0.5, ge=-1.0, le=1.0)
    shared_history: str = ""
    potential_conflicts: list[str] = Field(default_factory=list)


class SharedHistoryValidation(BaseModel):
    from_id: str
    to_id: str
    is_valid: bool
    issues: list[str] = Field(default_factory=list)
    perspective_distortion_detected: bool = False


class GenerationMetrics(BaseModel):
    cloud_tokens_input: int = 0
    cloud_tokens_output: int = 0
    cloud_cost: float = 0.0
    cloud_call_count: int = 0
    local_call_count: int = 0


class WorldsmithGenerateRequest(BaseModel):
    description: str
    num_characters: int = Field(default=3, ge=2, le=10)


class CharacterBatchRequest(BaseModel):
    world_description: str
    locations: list[str]  # location names
    num_characters: int = Field(default=3, ge=2, le=10)


class RelationshipGenerateRequest(BaseModel):
    characters: list[CharacterConfig]
