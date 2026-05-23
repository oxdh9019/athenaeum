"""v07_agent 独立验证脚本"""
import asyncio
import sys
sys.path.insert(0, '.')

from core.v07_agent import V07Agent


class MockWorld:
    """模拟 World 对象"""
    class MockTimeOfDay:
        value = "morning"
    class MockWeather:
        value = "clear"
    class MockTickType:
        value = "active"

    _tick_id = 100
    _game_hour = 8
    current_tick_type = MockTickType()
    _time_of_day = MockTimeOfDay()
    _weather = MockWeather()

    def neighbors_of(self, agent_id):
        return []

    def move_agent(self, agent_id, location):
        print(f"  [移动] {agent_id} -> {location}")


class MockLLM:
    """模拟 LLM"""
    async def chat(self, messages, system, temperature, max_tokens):
        return '{"action_type": "move", "target": "library", "urgency": 0.7, "reasoning": "推进目标"}'


async def test_v07_agent():
    print("=== V07Agent 独立验证 ===\n")

    soul = {
        "core_desires": [
            {"name": "知识追求", "level": 0.8},
            {"name": "被人认可", "level": 0.6},
        ],
        "long_term_goals": [
            {"description": "完成一本书的写作"},
        ],
    }

    agent = V07Agent(
        agent_id="char_v07",
        name="艾琳",
        personality={"openness": 0.7, "conscientiousness": 0.6, "extraversion": 0.4, "neuroticism": 0.3},
        occupation="scholar",
        soul=soul,
        llm=MockLLM(),
        world=MockWorld(),
        initial_location="宿舍",
    )

    print("Step 1: V07Agent 初始化完成")
    print(f"  - 目标管理器: {agent.goal_manager}")
    print(f"  - 情绪模型: {agent.emotion_model}")
    print(f"  - 心跳模式: {agent.heartbeat_mode}")

    print("\nStep 2: 活跃目标")
    active_goal = agent.goal_manager.active_goal
    if active_goal:
        print(f"  - [{active_goal.goal_type.value}] {active_goal.description}")
        print(f"    优先级: {active_goal.priority:.1f}, 进度: {active_goal.progress:.0%}")

    print("\nStep 3: 日程规划")
    routine = agent._daily_planner.routine
    for entry in routine:
        print(f"  - [{entry.period}] {entry.description} (p={entry.probability})")

    print("\nStep 4: 情绪状态")
    emotion = agent.get_emotion_state()
    print(f"  - {emotion}")

    print("\nStep 5: 心跳间隔")
    hb = agent.heartbeat_mode
    print(f"  - 当前间隔: {hb.get_interval()} Tick")
    print(f"  - 状态: {hb.get_status()}")

    print("\nStep 6: decide_action (模拟一次决策)")
    env_state = {"time_of_day": "morning", "weather": "clear"}
    action = await agent.decide_action("active", env_state, [])
    print(f"  - 决策结果: {action}")

    print("\nStep 7: 性格过滤后的 prompt 构建")
    prompt = agent._build_behavior_prompt(env_state, [], [], "")
    print(f"  - Prompt 长度: {len(prompt)} 字符")
    print(f"  - 包含目标状态: {'当前目标' in prompt}")
    print(f"  - 包含情绪状态: {'情绪状态' in prompt}")

    print("\n=== 验证完成 ===")


if __name__ == "__main__":
    asyncio.run(test_v07_agent())