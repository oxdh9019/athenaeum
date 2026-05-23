#!/usr/bin/env python3
"""
main.py — V0.1 单 Agent 对话原型入口
命令行交互循环
"""

import asyncio
import logging
from pathlib import Path

from agent import Agent, CharacterConfig
from llm_gateway import LLMGateway
from utils import load_character

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_character_info(config: CharacterConfig):
    """打印角色介绍"""
    print(f"\n{'='*50}")
    print(f"  {config.name} — AI 角色社交模拟 · V0.1")
    print(f"{'='*50}")
    print(f"  年龄: {config.age}岁 | 性别: {config.gender} | 代词: {config.pronouns}")
    print(f"  身份: {' / '.join([config.identity_tags['primary']] + config.identity_tags.get('secondary', []))}")
    print(f"  自我认同: {config.identity_tags.get('self_identity', 'N/A')}")
    print(f"{'='*50}\n")


async def main():
    # 加载角色配置
    script_dir = Path(__file__).parent
    config_path = script_dir / "character.yaml"
    config = load_character(str(config_path))

    # 初始化 LLM 网关
    llm = LLMGateway()

    # 初始化 Agent
    agent = Agent(config, llm)

    print_character_info(config)
    print("输入 /quit 退出 | /stat 查看状态 | /desire 查看当前欲望\n")

    while True:
        try:
            user_input = await asyncio.to_thread(
                lambda: input(f"你: ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n\n退出。")
            break

        if not user_input:
            continue

        cmd = user_input.split()[0].lower()

        if cmd == "/quit":
            print(f"\n[对话结束] 共 {agent.memory_count} 条记忆 | "
                  f"累计Token: {agent.total_tokens} | "
                  f"累计成本: ${agent.total_cost:.4f}")
            await llm.close()
            break

        if cmd == "/stat":
            print(f"\n[状态]")
            print(f"  记忆条数: {agent.memory_count}/{agent._memory._max}")
            print(f"  累计Token: {agent.total_tokens}")
            print(f"  累计成本: ${agent.total_cost:.4f}")
            print(f"  LLM调用: {llm.usage.call_count}")
            print()
            continue

        if cmd == "/desire":
            d = agent._desire
            print(f"\n[欲望状态]")
            print(f"  TR (威胁感知): {d.TR:.2f}")
            print(f"  CS (舒适度):   {d.CS:.2f}")
            print(f"  SA (社交认可): {d.SA:.2f}")
            print()
            continue

        # 正常对话
        print(f"\n{agent.name} 正在思考...")
        reply = await agent.respond(user_input)
        print(f"{agent.name}: {reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
