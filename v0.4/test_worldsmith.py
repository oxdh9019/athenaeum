"""
test_worldsmith.py — V0.4 世界工坊测试
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


class MockLLM:
    """模拟 LLM 客户端"""

    def __init__(self, responses: dict = None):
        self._responses = responses or {}
        self._call_count = 0
        self._last_messages = []

    async def chat(self, messages, system=None, temperature=0.7, max_tokens=1000) -> str:
        self._call_count += 1
        self._last_messages = messages

        # 返回预设响应
        for pattern, response in self._responses.items():
            if pattern in str(messages):
                return response

        return '{"name": "测试世界", "description": "测试", "locations": [], "time_rules": {}, "atmosphere": {}}'


@pytest.fixture
def mock_cloud_llm():
    return MockLLM({
        "世界": '{"name": "翡翠城", "description": "一个中世纪风格的小镇", "locations": [{"id": "library", "name": "图书馆", "description": "安静的阅读场所", "tags": ["indoor", "social"], "capacity": 10}], "time_rules": {"day_start_hour": 8, "day_end_hour": 22, "tick_interval_minutes": 60}, "atmosphere": {"mood": "宁静", "dominant_themes": ["知识", "平和"], "ambient_sounds": ["翻书声"]}}',
        "角色": '{"characters": [{"id": "char_1", "name": "艾琳", "age": 35, "gender": "女", "pronouns": "她", "identity_tags": {"primary": "图书馆管理员", "secondary": [], "self_identity": "知识守护者"}, "social_background": {}, "personality": {"openness": 0.8, "conscientiousness": 0.9, "extraversion": 0.3, "agreeableness": 0.7, "neuroticism": 0.4}, "extended_personality": {"empathy": 0.6, "humor": 0.3, "ambition": 0.4, "loyalty": 0.8, "courage": 0.5, "patience": 0.9, "generosity": 0.5}, "backstory": {"title": "图书馆的管理者", "childhood": "", "adolescence": "", "adulthood": "", "present": "在图书馆工作，喜欢安静", "turning_points": []}, "needs": [{"name": "safety", "level": 0.5}, {"name": "belonging", "level": 0.6}], "initial_location": "图书馆"}]}',
        "关系": '{"from_id": "char_1", "to_id": "char_2", "relationship_type": "friend", "strength": 0.7, "shared_history": "她们是多年的朋友，一起经历了许多事情。"}',
    })


@pytest.fixture
def mock_local_llm():
    return MockLLM({
        "自我介绍": "我叫艾琳，是这座图书馆的管理员。我热爱书籍和安静的阅读环境。",
        "视角": '{"from_id": "char_1", "to_id": "char_2", "is_valid": true, "issues": [], "perspective_distortion_detected": false}',
    })


@pytest.mark.asyncio
async def test_world_generation(mock_cloud_llm, mock_local_llm):
    """测试世界骨架生成"""
    from world_models import WorldsmithGenerateRequest
    from worldsmith import Worldsmith

    worldsmith = Worldsmith(mock_cloud_llm, mock_local_llm)
    request = WorldsmithGenerateRequest(description="一个中世纪风格的小镇")

    result = await worldsmith.generate_full_world(request)

    # 验证返回值结构
    assert "world" in result
    assert "characters" in result
    assert "relationships" in result
    assert "metrics" in result

    # 验证世界数据
    world = result["world"]
    assert world.name == "翡翠城"
    assert len(world.locations) >= 1

    # 验证角色数据
    characters = result["characters"]
    assert len(characters) >= 1
    char = characters[0]
    assert char.name == "艾琳"
    assert hasattr(char, "personality")
    assert hasattr(char, "introduce_text")


@pytest.mark.asyncio
async def test_character_generation(mock_cloud_llm, mock_local_llm):
    """测试角色批量生成"""
    from world_models import CharacterBatchRequest
    from worldsmith import Worldsmith

    worldsmith = Worldsmith(mock_cloud_llm, mock_local_llm)
    request = CharacterBatchRequest(
        world_description="一个中世纪风格的小镇",
        locations=["图书馆", "面包店", "广场"],
        num_characters=3,
    )

    characters = await worldsmith.generate_characters(request)

    assert len(characters) >= 1
    for char in characters:
        assert char.id
        assert char.name
        assert hasattr(char, "personality")
        assert hasattr(char, "introduce_text")


@pytest.mark.asyncio
async def test_relationship_generation(mock_cloud_llm, mock_local_llm):
    """测试关系编织"""
    from world_models import CharacterConfig, BigFivePersonality
    from worldsmith import Worldsmith

    worldsmith = Worldsmith(mock_cloud_llm, mock_local_llm)

    # 创建测试角色
    char1 = CharacterConfig(
        id="char_1",
        name="艾琳",
        age=35,
        gender="女",
        personality=BigFivePersonality(),
        identity_tags=MagicMock(primary="图书馆管理员"),
        backstory=MagicMock(),
    )
    char2 = CharacterConfig(
        id="char_2",
        name="马克",
        age=40,
        gender="男",
        personality=BigFivePersonality(),
        identity_tags=MagicMock(primary="面包师"),
        backstory=MagicMock(),
    )

    relationships = await worldsmith.generate_relationships([char1, char2])

    assert len(relationships) >= 1
    rel = relationships[0]
    assert rel.from_id == "char_1"
    assert rel.to_id == "char_2"
    assert rel.relationship_type


@pytest.mark.asyncio
async def test_introduce_text_generation(mock_local_llm):
    """测试 introduce_text 本地生成"""
    from world_models import CharacterConfig, BigFivePersonality
    from worldsmith import Worldsmith

    worldsmith = Worldsmith(mock_local_llm, mock_local_llm)

    char = CharacterConfig(
        id="char_1",
        name="艾琳",
        age=35,
        gender="女",
        personality=BigFivePersonality(openness=0.8, conscientiousness=0.9),
        identity_tags=MagicMock(primary="图书馆管理员", self_identity="知识守护者"),
        backstory=MagicMock(),
    )

    updated = await worldsmith._generate_introduce_texts([char])

    assert len(updated) == 1
    assert updated[0].introduce_text


@pytest.mark.asyncio
async def test_metrics_tracking(mock_cloud_llm, mock_local_llm):
    """测试 Token 消耗追踪"""
    from world_models import WorldsmithGenerateRequest
    from worldsmith import Worldsmith

    worldsmith = Worldsmith(mock_cloud_llm, mock_local_llm)
    request = WorldsmithGenerateRequest(description="测试世界", num_characters=2)

    await worldsmith.generate_full_world(request)

    metrics = worldsmith.metrics
    assert metrics.cloud_call_count > 0
    assert metrics.local_call_count >= 0


@pytest.mark.asyncio
async def test_perspective_validation(mock_cloud_llm, mock_local_llm):
    """测试视角扭曲检测"""
    from world_models import CharacterConfig, BigFivePersonality, CharacterPairRelationship
    from worldsmith import Worldsmith

    worldsmith = Worldsmith(mock_cloud_llm, mock_local_llm)

    rel = CharacterPairRelationship(
        from_id="char_1",
        to_id="char_2",
        relationship_type="friend",
        strength=0.7,
        shared_history="艾琳认为马克是她最好的朋友，但马克对此有不同看法。",
    )

    validations = await worldsmith._validate_shared_histories([rel], [])

    assert len(validations) == 1
    # 本地LLM返回的mock数据应该is_valid为true


def test_big_five_personality_model():
    """测试 BigFivePersonality 模型"""
    from world_models import BigFivePersonality

    p = BigFivePersonality(
        openness=0.8,
        conscientiousness=0.9,
        extraversion=0.3,
        agreeableness=0.7,
        neuroticism=0.4,
    )

    assert p.openness == 0.8
    assert p.conscientiousness == 0.9


def test_character_config_model():
    """测试 CharacterConfig 模型"""
    from world_models import CharacterConfig, BigFivePersonality

    char = CharacterConfig(
        id="test_1",
        name="测试角色",
        age=30,
        gender="男",
        personality=BigFivePersonality(),
    )

    assert char.id == "test_1"
    assert char.name == "测试角色"
    assert char.age == 30


def test_generated_world_model():
    """测试 GeneratedWorld 模型"""
    from world_models import GeneratedWorld, LocationModel, WorldTimeRules, WorldAtmosphere

    world = GeneratedWorld(
        name="测试世界",
        description="一个测试世界",
        locations=[
            LocationModel(
                id="loc_1",
                name="测试地点",
                description="描述",
                tags=["indoor"],
                capacity=5,
            )
        ],
        time_rules=WorldTimeRules(),
        atmosphere=WorldAtmosphere(mood="测试"),
    )

    assert world.name == "测试世界"
    assert len(world.locations) == 1
    assert world.locations[0].name == "测试地点"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
