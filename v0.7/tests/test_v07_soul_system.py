"""
test_v07_soul_system.py — V0.7 灵魂系统测试
测试目标生成、情绪更新、过滤规则、条件反思、故事模式

作为脚本运行（从 v0.7/ 目录）:
    python tests/test_v07_soul_system.py
退出码 0 = 全部通过，非 0 = 有失败。
"""
import asyncio
import random
import sys
import traceback

sys.path.insert(0, '.')

from server.core.subconscious_engine import SubconsciousEngine, SoulConfig, SubconsciousRule
from server.core.story_mode import StoryMode, StoryManager, StoryConfig, StoryStatus
from server.core.emotion_model import EmotionModel
from server.core.personality_filter import PersonalityFilter
from server.core.goal_manager import GoalManager, GoalType, GoalStatus


# ---- 简单的测试结果跟踪 ----
class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []  # (name, message)

    def run(self, name, fn):
        print(f"\n=== {name} ===")
        try:
            fn()
        except AssertionError as e:
            self.failed += 1
            self.errors.append((name, str(e) or "断言失败（无消息）"))
            print(f"  ✗ FAIL: {e}")
        except Exception as e:
            self.failed += 1
            tb = traceback.format_exc()
            self.errors.append((name, f"异常: {e}\n{tb}"))
            print(f"  ✗ ERROR: {e}")
            traceback.print_exc()
        else:
            self.passed += 1
            print(f"  ✓ PASS")

    def summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 50)
        print(f"测试结果: {self.passed}/{total} 通过, {self.failed} 失败")
        if self.errors:
            print("-" * 50)
            for name, msg in self.errors:
                print(f"[{name}]\n{msg}\n")
        print("=" * 50)
        return self.failed == 0


runner = TestRunner()


def test_subconscious_engine():
    """测试潜意识引擎"""
    random.seed(42)  # 让概率分支确定性

    soul = SoulConfig(
        core_desires=[{"name": "知识", "level": 0.8}],
        inner_conflict={
            "pole_a": "渴望知识的自由传播",
            "pole_b": "害怕古籍被不当使用而损毁",
            "description": "艾琳常常在借出珍本与保护古籍之间挣扎",
        },
        subconscious_rules=[
            {"trigger": "看到甜食", "action": "目光多停留几秒，可能微笑", "priority": 0.3},
            {"trigger": "古籍", "action": "手指轻轻触碰书脊", "priority": 0.5},
            {"trigger": "窗外", "action": "若有所思地望向窗外", "priority": 0.2},
        ],
    )

    engine = SubconsciousEngine("agent_ailin", soul)
    assert engine._agent_id == "agent_ailin"
    assert len(engine._rules) == 3, f"应有 3 条规则，实际 {len(engine._rules)}"

    class MockAgent:
        id = "agent_ailin"
        name = "艾琳"

    world_snapshot = {
        "location": "图书馆",
        "visible_objects": ["古籍", "茶杯", "窗外的花园"],
        "nearby_agents": ["agent_wang"],
        "time_of_day": "下午",
    }

    # 至少 1 次应该能匹配到（古籍 优先级 0.5 最高，且在 visible_objects 里）
    # 跑 10 次确保统计上必然命中
    matched = 0
    for _ in range(10):
        result = engine.match(MockAgent(), world_snapshot)
        if result is not None:
            matched += 1
            assert "micro_action" in result, "match() 返回值缺 micro_action"
            assert "priority" in result
            assert "rule_trigger" in result
    assert matched > 0, f"10 次 match() 全部返回 None — 潜意识引擎失效"

    # 多次调用 get_micro_action_for_dialogue，应返回 str 或 None，不抛异常
    out = engine.get_micro_action_for_dialogue(
        MockAgent(), world_snapshot, emotion_arousal=0.7
    )
    assert out is None or isinstance(out, str), f"micro_action 类型错误: {type(out)}"

    status = engine.get_status()
    assert isinstance(status, dict)
    assert status.get("rule_count") == 3
    assert isinstance(status.get("active_rules"), list)


def test_emotion_model():
    """测试情绪模型"""
    emotion = EmotionModel("agent_ailin", initial_valence=0.0, initial_arousal=0.3)

    state = emotion.get_state()
    assert -1.0 <= state["valence"] <= 1.0
    assert 0.0 <= state["arousal"] <= 1.0
    assert state["label"] in {"happy", "content", "anxious", "sad", "curious", "neutral"}
    print(f"  初始: {state['label']} (valence={state['valence']:.2f})")

    # 欲望满足 + 社交反馈：valence 应上升
    v0 = emotion.valence
    emotion.update(desire_fulfillment=0.8, goal_progress=0.1, social_feedback=0.2)
    state = emotion.get_state()
    assert emotion.valence > v0, f"欲望满足后 valence 应上升: {v0:.2f} -> {emotion.valence:.2f}"
    assert -1.0 <= state["valence"] <= 1.0

    # 危险事件：arousal 大幅上升
    a0 = emotion.arousal
    emotion.apply_event("danger")
    assert emotion.arousal > a0, f"danger 事件应提升 arousal: {a0:.2f} -> {emotion.arousal:.2f}"
    assert 0.0 <= emotion.arousal <= 1.0

    # 正向社交：valence 上升
    v1 = emotion.valence
    emotion.apply_event("positive_social")
    assert emotion.valence > v1, f"positive_social 应提升 valence: {v1:.2f} -> {emotion.valence:.2f}"


def test_personality_filter():
    """测试性格过滤"""
    high_neuro = {
        "neuroticism": 0.8,
        "extraversion": 0.5,
        "openness": 0.5,
        "conscientiousness": 0.5,
        "agreeableness": 0.5,
    }
    flt = PersonalityFilter(high_neuro)

    # 高神经质 + 高风险意图：应该大概率被否决（70% 概率）
    intent_risky = {"action_type": "confront", "urgency": 0.7, "reasoning": "测试"}
    random.seed(7)
    blocked = 0
    trials = 100
    for _ in range(trials):
        if flt.filter(dict(intent_risky)) is None:
            blocked += 1
    assert blocked > trials * 0.5, (
        f"高神经质应否决 >50% 高风险意图，实际 {blocked}/{trials}"
    )

    # 低外向性 + 社交意图：urgency 应被削弱
    low_extra = {
        "neuroticism": 0.3,
        "extraversion": 0.2,
        "openness": 0.5,
        "conscientiousness": 0.5,
        "agreeableness": 0.5,
    }
    flt2 = PersonalityFilter(low_extra)
    intent_social = {"action_type": "greet_stranger", "urgency": 0.6, "reasoning": "测试"}
    result = flt2.filter(dict(intent_social))
    assert result is not None, "低外向性不应否决 greet_stranger"
    assert result["urgency"] < 0.6, (
        f"低外向性应削弱 greet_stranger urgency: 0.6 -> {result['urgency']:.2f}"
    )

    # 行动风格应是非空字符串
    style = flt2.get_action_style()
    assert isinstance(style, dict)
    assert isinstance(style.get("style_description"), str)
    assert len(style["style_description"]) > 0


def test_goal_manager():
    """测试目标管理"""
    soul = {
        "core_desires": [
            {"name": "知识传播", "level": 0.8},
            {"name": "古籍保护", "level": 0.9},
        ],
        "long_term_goals": [
            {"description": "完成一本关于古籍修复的专著"},
        ],
    }
    personality = {
        "openness": 0.7,
        "conscientiousness": 0.8,
        "extraversion": 0.4,
    }

    manager = GoalManager("agent_ailin", personality)

    async def run_test():
        goals = await manager.generate_goals_from_soul(
            soul, personality, current_location="图书馆", existing_relationships=[]
        )
        # 至少应该有: 2 core_desires + 1 long_term_goal = 3 个
        assert len(goals) >= 3, f"至少应生成 3 个目标，实际 {len(goals)}"
        for goal in goals:
            assert isinstance(goal.goal_type, GoalType)
            assert isinstance(goal.description, str)
            assert 0.0 <= goal.priority <= 1.0
            assert 0.0 <= goal.progress <= 1.0

        if goals:
            goal = goals[0]
            assert goal.progress == 0.0
            completed = await manager.update_goal_progress(goal.goal_id, 0.3)
            assert isinstance(completed, bool)
            # 注意：0.3 增量可能不会让目标完成
            if completed:
                assert goal.progress >= 1.0 - 1e-9

        intent = manager.get_current_intent()
        assert isinstance(intent, dict)
        assert "active_goal" in intent, f"get_current_intent() 缺 'active_goal': {intent}"
        assert "goal_type" in intent

    asyncio.run(run_test())


def test_story_mode():
    """测试故事模式"""
    async def run():
        story = StoryMode(
            story_id="test_story_1",
            config=StoryConfig(max_ticks=50, min_ticks=10),
        )
        assert story.status == StoryStatus.IDLE

        story.start(start_tick=0, tick_limit=30)
        assert story.status == StoryStatus.RUNNING
        assert story._start_tick == 0

        # 模拟 Tick 更新（"我们今天聊得很开心" 不含默认结束关键词，不会触发 end）
        for tick in range(1, 21):
            should_end = story.tick_update(
                current_tick=tick,
                active_goals=[],
                recent_dialogues=[
                    {"utterance": "我们今天聊得很开心"},
                ] if tick == 15 else [],
                relationship_changes=[0.3] if tick == 10 else [],
            )
            if should_end:
                break

        # 跑到 tick 20 (start=0, limit=30) 不会自然结束
        assert story._events is not None
        status = story.get_status()
        assert status["story_id"] == "test_story_1"
        assert status["event_count"] >= 0

        # 故事管理器
        manager = StoryManager()
        story2 = manager.create_story(max_ticks=100, min_ticks=20)
        assert story2.story_id in manager._stories
        listed = manager.list_stories()
        assert len(listed) == 1
        assert listed[0]["story_id"] == story2.story_id

        # 手动结束 — 必须在运行中的 event loop 里调用，因为
        # _trigger_end 内部用 asyncio.create_task 启动摘要生成 task
        story2.start(start_tick=0, tick_limit=100)
        assert story2.status == StoryStatus.RUNNING
        ok = manager.end_story(story2.story_id)
        assert ok is True

        # 让后台的 _generate_summary 跑完，避免 "coroutine was never awaited" 警告
        await asyncio.sleep(0)

    asyncio.run(run())


def main():
    print("=" * 50)
    print("V0.7 灵魂系统测试")
    print("=" * 50)

    runner.run("SubconsciousEngine", test_subconscious_engine)
    runner.run("EmotionModel", test_emotion_model)
    runner.run("PersonalityFilter", test_personality_filter)
    runner.run("GoalManager", test_goal_manager)
    runner.run("StoryMode", test_story_mode)

    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
