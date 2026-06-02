# V0.7 灵魂系统测试（pytest 形式）
#
# 覆盖 core/{subconscious_engine, emotion_model, personality_filter, goal_manager, story_mode}
# 这些是 V0.7 的"灵魂"层，没有外部依赖，可在 <1s 内跑完。
#
# 运行：
#   cd v0.7/server
#   pytest tests/test_soul_pytest.py
#   pytest tests/test_soul_pytest.py --cov=core --cov-report=term-missing
#
# 与 tests/test_v07_soul_system.py 的区别：那个是 plain script 形式（CI 用），
# 这里是 pytest 标准形式（开发时用，享受 --cov 覆盖率报告 + IDE 集成）。

import random
from unittest.mock import MagicMock

import pytest

from core.subconscious_engine import SubconsciousEngine, SoulConfig
from core.emotion_model import EmotionModel
from core.personality_filter import PersonalityFilter
from core.goal_manager import GoalManager, GoalType
from core.story_mode import StoryMode, StoryManager, StoryConfig, StoryStatus


class TestSubconsciousEngine:
    def test_engine_constructs_with_soul(self):
        soul = SoulConfig(
            core_desires=[{"name": "知识", "level": 0.8}],
            subconscious_rules=[
                {"trigger": "古籍", "action": "触碰书脊", "priority": 0.5},
            ],
        )
        engine = SubconsciousEngine("a1", soul)
        assert engine._agent_id == "a1"
        assert len(engine._rules) == 1

    def test_match_returns_micro_action_or_none(self):
        random.seed(42)
        soul = SoulConfig(
            subconscious_rules=[
                {"trigger": "古籍", "action": "触碰书脊", "priority": 0.5},
            ],
        )
        engine = SubconsciousEngine("a1", soul)
        agent = MagicMock()
        agent.id = "a1"
        agent.name = "A"
        world = {
            "location": "图书馆",
            "visible_objects": ["古籍"],
            "nearby_agents": [],
            "time_of_day": "下午",
        }
        out = engine.match(agent, world)
        # 至少 1 次会命中
        matched_count = sum(1 for _ in range(10) if engine.match(agent, world) is not None)
        assert matched_count > 0

    def test_get_status_shape(self):
        engine = SubconsciousEngine("a1", SoulConfig(subconscious_rules=[]))
        status = engine.get_status()
        assert isinstance(status, dict)
        assert "rule_count" in status
        assert "active_rules" in status


class TestEmotionModel:
    def test_initial_state(self):
        em = EmotionModel("a1", initial_valence=0.0, initial_arousal=0.3)
        s = em.get_state()
        assert -1.0 <= s["valence"] <= 1.0
        assert 0.0 <= s["arousal"] <= 1.0
        assert s["label"] in {"happy", "content", "anxious", "sad", "curious", "neutral"}

    def test_desire_fulfillment_raises_valence(self):
        em = EmotionModel("a1")
        v0 = em.valence
        em.update(desire_fulfillment=0.8, goal_progress=0.1, social_feedback=0.2)
        assert em.valence > v0

    def test_danger_event_raises_arousal(self):
        em = EmotionModel("a1")
        a0 = em.arousal
        em.apply_event("danger")
        assert em.arousal > a0
        assert 0.0 <= em.arousal <= 1.0

    def test_clamp_under_extreme_input(self):
        em = EmotionModel("a1")
        for _ in range(50):
            em.adjust_valence(10.0)
            em.adjust_arousal(10.0)
        assert -1.0 <= em.valence <= 1.0
        assert 0.0 <= em.arousal <= 1.0


class TestPersonalityFilter:
    def test_high_neuroticism_blocks_most_risky_intents(self):
        flt = PersonalityFilter({
            "neuroticism": 0.8, "extraversion": 0.5, "openness": 0.5,
            "conscientiousness": 0.5, "agreeableness": 0.5,
        })
        random.seed(7)
        blocked = sum(
            1 for _ in range(100)
            if flt.filter({"action_type": "confront", "urgency": 0.7, "reasoning": "test"}) is None
        )
        assert blocked > 50, f"高神经质应否决 >50% 高风险意图，实际 {blocked}/100"

    def test_low_extraversion_softens_social_urgency(self):
        flt = PersonalityFilter({
            "neuroticism": 0.3, "extraversion": 0.2, "openness": 0.5,
            "conscientiousness": 0.5, "agreeableness": 0.5,
        })
        result = flt.filter({"action_type": "greet_stranger", "urgency": 0.6, "reasoning": "test"})
        assert result is not None
        assert result["urgency"] < 0.6

    def test_action_style_describes(self):
        flt = PersonalityFilter({
            "neuroticism": 0.5, "extraversion": 0.5, "openness": 0.5,
            "conscientiousness": 0.5, "agreeableness": 0.5,
        })
        style = flt.get_action_style()
        assert isinstance(style, dict)
        assert isinstance(style.get("style_description"), str)
        assert len(style["style_description"]) > 0


class TestGoalManager:
    @pytest.mark.asyncio
    async def test_generate_goals_from_soul(self):
        gm = GoalManager("a1", {"openness": 0.7, "conscientiousness": 0.8, "extraversion": 0.4})
        soul = {
            "core_desires": [
                {"name": "知识传播", "level": 0.8},
                {"name": "古籍保护", "level": 0.9},
            ],
            "long_term_goals": [
                {"description": "完成一本关于古籍修复的专著"},
            ],
        }
        goals = await gm.generate_goals_from_soul(
            soul, gm._personality, current_location="图书馆", existing_relationships=[]
        )
        assert len(goals) >= 3
        for g in goals:
            assert isinstance(g.goal_type, GoalType)
            assert isinstance(g.description, str)
            assert 0.0 <= g.priority <= 1.0
            assert 0.0 <= g.progress <= 1.0

    @pytest.mark.asyncio
    async def test_get_current_intent_shape(self):
        gm = GoalManager("a1", {"openness": 0.5, "conscientiousness": 0.5, "extraversion": 0.5})
        intent = gm.get_current_intent()
        assert isinstance(intent, dict)
        assert "active_goal" in intent
        assert "goal_type" in intent


@pytest.mark.asyncio
class TestStoryMode:
    async def test_story_lifecycle(self):
        story = StoryMode(
            story_id="t1",
            config=StoryConfig(max_ticks=50, min_ticks=10),
        )
        assert story.status == StoryStatus.IDLE

        story.start(start_tick=0, tick_limit=30)
        assert story.status == StoryStatus.RUNNING

        for tick in range(1, 21):
            should_end = story.tick_update(
                current_tick=tick,
                active_goals=[],
                recent_dialogues=[{"utterance": "我们今天聊得很开心"}] if tick == 15 else [],
                relationship_changes=[0.3] if tick == 10 else [],
            )
            if should_end:
                break

        status = story.get_status()
        assert status["story_id"] == "t1"
        assert status["event_count"] >= 0

    async def test_story_manager(self):
        manager = StoryManager()
        story = manager.create_story(max_ticks=100, min_ticks=20)
        assert story.story_id in manager._stories
        listed = manager.list_stories()
        assert len(listed) == 1

        story.start(start_tick=0, tick_limit=100)
        ok = manager.end_story(story.story_id)
        assert ok is True
        # 让后台摘要 task 跑完
        import asyncio
        await asyncio.sleep(0)
