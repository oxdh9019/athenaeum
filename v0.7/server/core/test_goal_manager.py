"""goal_manager 独立验证脚本"""
import asyncio
from core.goal_manager import GoalManager, GoalType, GoalStatus

async def test_goal_manager():
    print("=== GoalManager 独立验证 ===\n")

    agent_id = "test_char_1"
    gm = GoalManager(agent_id, personality={"openness": 0.7, "conscientiousness": 0.6})

    # 模拟 Soul 配置
    soul = {
        "core_desires": [
            {"name": "知识追求", "level": 0.8},
            {"name": "被人认可", "level": 0.6},
        ],
        "long_term_goals": [
            {"description": "完成一本书的写作"},
        ],
        "behavioral_tendencies": {
            "preferred_times": {"morning": "work"},
        }
    }

    personality = {"openness": 0.7, "conscientiousness": 0.6, "extraversion": 0.4}
    existing_rels = [{"to_id": "char_2", "strength": 0.5}]

    print("Step 1: generate_goals_from_soul()")
    goals = await gm.generate_goals_from_soul(soul, personality, "图书馆", existing_rels)
    print(f"  生成目标数: {len(goals)}")
    for g in goals:
        print(f"  - [{g.goal_type.value}] {g.description} (优先级: {g.priority:.1f}, 状态: {g.status.value})")

    print(f"\nStep 2: active_goal = {gm.active_goal.description if gm.active_goal else 'None'}")
    print(f"  pending_count = {gm.get_pending_count()}")

    print(f"\nStep 3: get_current_intent()")
    intent = gm.get_current_intent()
    print(f"  {intent}")

    print(f"\nStep 4: update_goal_progress()")
    if gm.active_goal:
        goal_id = gm.active_goal.goal_id
        completed = await gm.update_goal_progress(goal_id, 0.3)
        print(f"  进度更新30%: completed={completed}, progress={gm.active_goal.progress:.0%}")

        completed = await gm.update_goal_progress(goal_id, 0.7)
        print(f"  进度更新70%: completed={completed}, progress={gm.active_goal.progress:.0%}")

    print(f"\nStep 5: all_goals 状态")
    for g in gm.all_goals:
        print(f"  - [{g.status.value}] {g.description}")

    print("\n=== 验证完成 ===")

if __name__ == "__main__":
    asyncio.run(test_goal_manager())