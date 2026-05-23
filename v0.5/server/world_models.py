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
            # Convert ['he', 'him', 'his'] to '他/他/他' or similar
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
