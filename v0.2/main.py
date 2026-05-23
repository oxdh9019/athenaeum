#!/usr/bin/env python3
"""
main.py — V0.2 双角色对话引擎入口
用法: python main.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

script_dir = Path(__file__).parent

# 添加 v0.1 到 path（放在后面，作为 fallback）
_v01 = script_dir.parent / "v0.1"
if str(_v01) not in sys.path:
    sys.path.append(str(_v01))

# 确保本模块优先（放在前面）
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from config import LLMConfig, DialogueConfig
from llm_gateway import LLMGateway
from agent import V02Agent
from intent_generator import IntentGenerator
from dialogue_generator import DialogueGenerator
from dialogue_engine import DialogueEngine

# 日志配置：文件记录所有日志，终端只显示警告及以上
log_file = script_dir / "dialogue.log"

# 清除默认处理器，避免重复输出
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

root_logger.setLevel(logging.DEBUG)

# 文件处理器：记录所有日志到文件
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

# 终端处理器：只显示 WARNING 及以上级别
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter(
    "[%(levelname)s] %(message)s"
))

root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# 禁用第三方库的 DEBUG 日志
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


def print_intro(agent_a, agent_b):
    print("\n" + "=" * 55)
    print("  V0.2 — 双角色对话引擎 · AI 社交模拟")
    print("=" * 55)
    print(f"  角色 A: {agent_a.name} — {agent_a.id}")
    print(f"  角色 B: {agent_b.name} — {agent_b.id}")
    print(f"  初始关系值: 0.6（好友）")
    print("=" * 55)
    print()
    print("命令:")
    print("  /possess A <消息>  — 附身角色 A，注入消息")
    print("  /possess B <消息>  — 附身角色 B，注入消息")
    print("  /release           — 退出附身")
    print("  /stat              — 显示当前统计")
    print("  /quit              — 退出程序")
    print()


async def run_console_loop(engine: DialogueEngine, agent_a, agent_b):
    """交互式命令循环"""
    print("\n[对话已启动，输入 /help 查看命令]\n")

    while True:
        try:
            user_input = await asyncio.to_thread(
                lambda: input("> ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue

        parts = user_input.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "/quit":
            print("正在结束对话...")
            engine._running = False
            break

        if cmd == "/help":
            print("/possess A <消息> — 附身角色 A\n"
                  "/possess B <消息> — 附身角色 B\n"
                  "/release          — 退出附身\n"
                  "/stat             — 显示统计\n"
                  "/quit             — 退出\n")
            continue

        if cmd == "/release":
            engine.release()
            print("[已退出附身模式]")
            continue

        if cmd == "/stat":
            s = engine.stats
            r = engine.relationship
            print(f"\n[统计]")
            print(f"  对话轮次: {s.total_turns}")
            print(f"  累计Token: {s.total_tokens}")
            print(f"  累计成本: ${s.total_cost:.4f}")
            print(f"  关系值: {r.strength:.3f}")
            print(f"  附身状态: {engine._possessed or '无'}\n")
            continue

        if cmd == "/possess":
            if len(parts) < 2:
                print("用法: /possess A <消息>")
                continue
            target = parts[1].upper()
            msg = parts[2] if len(parts) > 2 else ""
            if target not in ("A", "B"):
                print("目标必须是 A 或 B")
                continue
            agent_id = agent_a.id if target == "A" else agent_b.id
            engine.possess(agent_id, msg)
            agent_name = agent_a.name if target == "A" else agent_b.name
            print(f"[系统] 已附身 {agent_name}，下一句由你来说出: 「{msg}」")
            continue

        print(f"未知命令: {cmd}，输入 /help 查看帮助")


async def main():
    llm_cfg = LLMConfig()
    diag_cfg = DialogueConfig()

    llm = LLMGateway(model=llm_cfg.model)

    agent_a = V02Agent.from_yaml(script_dir / "character_a.yaml", llm)
    agent_b = V02Agent.from_yaml(script_dir / "character_b.yaml", llm)

    print_intro(agent_a, agent_b)

    intent_gen = IntentGenerator(llm)
    diag_gen = DialogueGenerator(llm)
    engine = DialogueEngine(
        agent_a=agent_a,
        agent_b=agent_b,
        intent_generator=intent_gen,
        dialogue_generator=diag_gen,
        max_turns=diag_cfg.max_turns,
        loop_threshold=diag_cfg.loop_similarity_threshold,
        loop_window=diag_cfg.loop_window,
        st_cache_dir=diag_cfg.st_cache_dir,
    )

    dialogue_task = asyncio.create_task(engine.run())
    console_task = asyncio.create_task(run_console_loop(engine, agent_a, agent_b))

    done, pending = await asyncio.wait(
        [dialogue_task, console_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for t in pending:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    stats = engine.stats
    rel = engine.relationship

    print("\n" + "=" * 55)
    print("  对话统计报告")
    print("=" * 55)
    print(f"  总对话轮次: {stats.total_turns}")
    print(f"  总Token: {stats.total_tokens}")
    print(f"  总成本: ${stats.total_cost:.4f}")
    print(f"  最终关系值: {rel.strength:.3f} "
          f"({'挚友' if rel.strength >= 0.8 else '好友' if rel.strength >= 0.5 else '熟人'})")
    print("=" * 55)

    await llm.close()


if __name__ == "__main__":
    asyncio.run(main())