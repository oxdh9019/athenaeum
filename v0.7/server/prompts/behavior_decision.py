"""
behavior_decision.py — V0.7 行为决策 prompt 模板

【为什么单独抽出来】
原 v07_agent.py:380-460 的 _build_behavior_prompt 是一个 80 行
f-string 拼接, 任何 prompt 调整都得改 agent 核心类。
这个模块把 prompt 抽到独立文件, 用 str.format 占位, 关键:

1. 所有「用户/历史可控」内容(记忆、目标描述、neighbors)
   走 utils.llm_parsing.inject_guard 截断 + 防注入
2. 模板 = 静态骨架 + {placeholders}, 调整骨架不碰 agent 逻辑
3. emotion_behavior_guide 这种枚举也抽常量, 改文案不动代码

【安全】
prompt 注入面 (audit 2.1):
- 短期记忆内容: 用户/角色生成的对话
- 长期 recall: archiver 摘要
- 目标描述: Worldsmith 生成, 可能是用户输入
- neighbor 名字: 用户配置

全部走 inject_guard, 失败回退到空字符串 + logger.warning。
"""
from typing import Optional

from utils.llm_parsing import inject_guard


EMOTION_BEHAVIOR_GUIDE: dict[str, str] = {
    "anxious": "你当前感到焦虑，倾向于谨慎行动，避免冒险",
    "happy": "你心情愉快，更愿意主动社交和尝试新事物",
    "sad": "你情绪低落，可能更倾向于独处和安静的活动",
    "content": "你感到满足，倾向于维持现状，保持平稳的行动节奏",
    "curious": "你充满好奇心，渴望探索新事物",
    "neutral": "你目前情绪平稳，行动理性",
}

EMOTION_DEFAULT_GUIDE = "你目前情绪平稳，行动理性"

ACTION_TYPES = ("move", "dialogue", "wait", "observe", "idle")

MAX_MEMORY_CHARS = 800
MAX_RECALL_CHARS = 400
MAX_GOAL_DESC_CHARS = 200
MAX_NEIGHBOR_CHARS = 100


_BEHAVIOR_PROMPT_TEMPLATE = """你是 {name}，目前在 {location}。

时间: {time_of_day} | 天气: {weather}
附近的人: {neighbors}

{memory_section}
{recall_section}

=== V0.7 角色状态 ===

当前目标: {active_goal}
目标类型: {goal_type}
目标进度: {goal_progress}
目标优先级: {goal_priority}{goal_deadline}

当前日程: {activity}

情绪状态: {emotion_label} (效价={valence}, 唤醒={arousal})
行为引导: {emotion_guide}

行动风格: {action_style}

请决定下一步行动。输出JSON格式：
{{"action_type": "move|dialogue|wait|observe|idle", "target": "位置名或角色ID或null", "urgency": 0.5, "reasoning": "为什么想这样做"}}

只输出JSON，不要其他内容。"""


def format_behavior_prompt(
    *,
    name: str,
    location: str,
    time_of_day: str,
    weather: str,
    neighbors: list[str],
    memory_context: list[dict],
    recall_section: str,
    goal_state: dict,
    goal_deadline: str,
    activity_desc: str,
    emotion_label: str,
    emotion_state: dict,
    action_style_desc: str,
) -> str:
    memory_lines = [
        f"- {m.get('role', '?')}: {inject_guard(m.get("content", ""), max_length=MAX_MEMORY_CHARS, purpose="memory")}"
        for m in (memory_context or [])[-5:]
    ]
    memory_section = ("\n最近记忆:\n" + "\n".join(memory_lines)) if memory_lines else ""

    safe_recall = inject_guard(recall_section or "", max_length=MAX_RECALL_CHARS, purpose="recall")
    recall_block = f"\n{ safe_recall }\n" if safe_recall else ""

    safe_neighbors = inject_guard(
        ", ".join(neighbors) if neighbors else "无",
        max_length=MAX_NEIGHBOR_CHARS,
        purpose="neighbors",
    )

    return _BEHAVIOR_PROMPT_TEMPLATE.format(
        name=name,
        location=location or "未知",
        time_of_day=time_of_day or "unknown",
        weather=weather or "unknown",
        neighbors=safe_neighbors,
        memory_section=memory_section,
        recall_section=recall_block,
        active_goal=inject_guard(
            goal_state.get("active_goal", "无特定目标") or "无特定目标",
            max_length=MAX_GOAL_DESC_CHARS,
            purpose="goal_desc",
        ),
        goal_type=goal_state.get("goal_type", "maintenance") or "maintenance",
        goal_progress=f"{float(goal_state.get('goal_progress', 0)):.0%}",
        goal_priority=f"{float(goal_state.get('goal_priority', 0)):.1f}",
        goal_deadline=goal_deadline or "",
        activity=inject_guard(activity_desc or "例行活动", max_length=MAX_GOAL_DESC_CHARS, purpose="activity"),
        emotion_label=emotion_label or "neutral",
        valence=f"{float(emotion_state.get('valence', 0)):.2f}",
        arousal=f"{float(emotion_state.get('arousal', 0)):.2f}",
        emotion_guide=EMOTION_BEHAVIOR_GUIDE.get(emotion_label or "neutral", EMOTION_DEFAULT_GUIDE),
        action_style=action_style_desc or "行为稳定",
    )
