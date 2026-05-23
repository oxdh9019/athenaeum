"""
test_v07_soul_system.py — V0.7 灵魂系统测试
测试目标生成、情绪更新、过滤规则、条件反思、故事模式
"""

import asyncio
import sys
sys.path.insert(0, '.')

from server.core.subconscious_engine import SubconsciousEngine, SoulConfig, SubconsciousRule
from server.core.story_mode import StoryMode, StoryManager, StoryConfig, StoryStatus
from server.core.emotion_model import EmotionModel
from server.core.personality_filter import PersonalityFilter
from server.core.goal_manager import GoalManager, GoalType, GoalStatus


def test_subconscious_engine():
    """测试潜意识引擎"""
    print("\n=== 测试 SubconsciousEngine ===")

    # 创建 Soul 配置
    soul = SoulConfig(
        core_desires=[{"name": "知识", "level": 0.8}],
        inner_conflict={
            "pole_a": "渴望知识的自由传播",
            "pole_b": "害怕古籍被不当使用而损毁",
            "description": "艾琳常常在借出珍本与保护古籍之间挣扎"
        },
        subconscious_rules=[
            {"trigger": "看到甜食", "action": "目光多停留几秒，可能微笑", "priority": 0.3},
            {"trigger": "古籍", "action": "手指轻轻触碰书脊", "priority": 0.5},
            {"trigger": "窗外", "action": "若有所思地望向窗外", "priority": 0.2},
        ]
    )

    engine = SubconsciousEngine("agent_ailin", soul)

    # 模拟世界快照
    world_snapshot = {
        "location": "图书馆",
        "visible_objects": ["古籍", "茶杯", "窗外的花园"],
        "nearby_agents": ["agent_wang"],
        "time_of_day": "下午"
    }

    class MockAgent:
        id = "agent_ailin"
        name = "艾琳"

    # 测试匹配
    result = engine.match(MockAgent(), world_snapshot)
    if result:
        print(f"✓ 匹配到潜意识动作: {result['micro_action']}")
        print(f"  触发词: {result['rule_trigger']}, 优先级: {result['priority']}")
    else:
        print("✗ 未匹配到潜意识动作")

    # 测试对话中生成 micro_action
    micro_action = engine.get_micro_action_for_dialogue(
        MockAgent(),
        world_snapshot,
        emotion_arousal=0.7
    )
    print(f"✓ 对话中 micro_action: {micro_action or '无'}")

    print("\nSubconsciousEngine 状态:")
    status = engine.get_status()
    print(f"  规则数量: {status['rule_count']}")
    print(f"  活跃规则: {status['active_rules']}")


def test_emotion_model():
    """测试情绪模型"""
    print("\n=== 测试 EmotionModel ===")

    emotion = EmotionModel("agent_ailin", initial_valence=0.0, initial_arousal=0.3)

    # 初始状态
    state = emotion.get_state()
    print(f"初始状态: {state['label']} (valence={state['valence']:.2f}, arousal={state['arousal']:.2f})")

    # 欲望满足 + 社交反馈
    emotion.update(desire_fulfillment=0.8, goal_progress=0.1, social_feedback=0.2)
    state = emotion.get_state()
    print(f"欲望满足+社交反馈后: {state['label']} (valence={state['valence']:.2f}, arousal={state['arousal']:.2f})")

    # 应用事件
    emotion.apply_event("danger")
    state = emotion.get_state()
    print(f"危险事件后: {state['label']} (valence={state['valence']:.2f}, arousal={state['arousal']:.2f})")

    emotion.apply_event("positive_social")
    state = emotion.get_state()
    print(f"正向社交后: {state['label']} (valence={state['valence']:.2f}, arousal={state['arousal']:.2f})")

    print("✓ EmotionModel 测试通过")


def test_personality_filter():
    """测试性格过滤"""
    print("\n=== 测试 PersonalityFilter ===")

    # 高神经质角色
    high_neuro = {
        "neuroticism": 0.8,
        "extraversion": 0.5,
        "openness": 0.5,
        "conscientiousness": 0.5,
        "agreeableness": 0.5,
    }

    filter_high_neuro = PersonalityFilter(high_neuro)

    # 测试高风险意图过滤
    intent_risky = {"action_type": "confront", "urgency": 0.7, "reasoning": "测试"}
    result = filter_high_neuro.filter(intent_risky)
    print(f"高神经质 + 高风险意图: {'✗ 否决' if result is None else '✓ 通过'}")

    # 低外向性角色
    low_extra = {
        "neuroticism": 0.3,
        "extraversion": 0.2,
        "openness": 0.5,
        "conscientiousness": 0.5,
        "agreeableness": 0.5,
    }

    filter_low_extra = PersonalityFilter(low_extra)

    # 测试社交意图削弱
    intent_social = {"action_type": "greet_stranger", "urgency": 0.6, "reasoning": "测试"}
    result = filter_low_extra.filter(intent_social)
    if result:
        print(f"低外向性 + 社交意图: ✓ 通过 (urgency {0.6} -> {result['urgency']:.2f})")

    # 获取行动风格
    style = filter_low_extra.get_action_style()
    print(f"行动风格: {style['style_description']}")

    print("✓ PersonalityFilter 测试通过")


def test_goal_manager():
    """测试目标管理"""
    print("\n=== 测试 GoalManager ===")

    soul = {
        "core_desires": [
            {"name": "知识传播", "level": 0.8},
            {"name": "古籍保护", "level": 0.9},
        ],
        "long_term_goals": [
            {"description": "完成一本关于古籍修复的专著"},
        ]
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
        print(f"生成了 {len(goals)} 个目标:")
        for goal in goals:
            print(f"  - {goal.description} (类型: {goal.goal_type.value}, 优先级: {goal.priority:.2f})")

        # 测试目标进度更新
        if goals:
            goal = goals[0]
            completed = await manager.update_goal_progress(goal.goal_id, 0.3)
            print(f"更新进度 30%: 完成={completed}, 当前进度={goal.progress:.0%}")

        # 获取当前意图
        intent = manager.get_current_intent()
        print(f"当前意图: {intent}")

    asyncio.run(run_test())

    print("✓ GoalManager 测试通过")


def test_story_mode():
    """测试故事模式"""
    print("\n=== 测试 StoryMode ===")

    story = StoryMode(
        story_id="test_story_1",
        config=StoryConfig(max_ticks=50, min_ticks=10),
    )

    story.start(start_tick=0, tick_limit=30)

    # 模拟 Tick 更新
    for tick in range(1, 21):
        should_end = story.tick_update(
            current_tick=tick,
            active_goals=[],
            recent_dialogues=[
                {"utterance": "我们今天聊得很开心"},  # 有结束关键词
            ] if tick == 15 else [],
            relationship_changes=[0.3] if tick == 10 else [],
        )

        if should_end:
            print(f"故事在 Tick {tick} 结束: {story.status}")
            break

    print(f"故事状态: {story.status.value}")
    print(f"事件数量: {len(story._events)}")

    # 测试故事管理器
    manager = StoryManager()
    story2 = manager.create_story(max_ticks=100, min_ticks=20)
    print(f"\n创建故事: {story2.story_id}")
    print(f"所有故事: {manager.list_stories()}")

    print("✓ StoryMode 测试通过")


def main():
    print("=" * 50)
    print("V0.7 灵魂系统测试")
    print("=" * 50)

    test_subconscious_engine()
    test_emotion_model()
    test_personality_filter()
    test_goal_manager()
    test_story_mode()

    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()