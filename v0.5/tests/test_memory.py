"""
test_memory.py — V0.5 记忆系统测试
验证归档、检索、遗忘链路
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "v0.3" / "server"))
sys.path.insert(0, str(project_root / "v0.5" / "server"))

from core.forgetting_curve import MemoryEntry, ForgettingCurve
from core.memory_archiver import MemoryArchiver
from core.memory_retriever import MemoryRetriever, RetrievedMemory


async def test_forgetting_curve():
    """测试遗忘曲线"""
    print("\n=== 测试遗忘曲线 ===")

    # 模拟角色神经质
    agent_id = "char_1"
    neuroticism = 0.6  # 高神经质，遗忘更慢

    curve = ForgettingCurve(agent_id, neuroticism)

    # 添加记忆
    memories = [
        MemoryEntry(
            memory_id="mem_1",
            agent_id=agent_id,
            content="今天在食堂和王淑芬聊天，她很热情地邀请我吃早餐",
            tick_created=10,
            importance=0.8,
            emotion="warm",
        ),
        MemoryEntry(
            memory_id="mem_2",
            agent_id=agent_id,
            content="和张志远讨论了催化反应的原理",
            tick_created=10,
            importance=0.6,
            emotion="curious",
        ),
        MemoryEntry(
            memory_id="mem_3",
            agent_id=agent_id,
            content="嗯，好的",
            tick_created=10,
            importance=0.2,
            emotion="neutral",
        ),
    ]

    for mem in memories:
        curve.add_memory(mem)

    print(f"初始记忆数量: {curve.size()}")

    # 测试不同 tick 的评分
    print("\n--- 记忆评分测试 ---")
    for tick in [10, 20, 30, 50, 100]:
        for mem in memories:
            score = mem.calculate_score(tick, neuroticism)
            print(f"Tick {tick}, {mem.memory_id}: score={score:.3f}, should_delete={mem.should_delete(tick, neuroticism)}")

    # 测试删除
    print("\n--- 记忆删除测试 ---")
    current_tick = 100
    deleted = curve.prune_memories(current_tick)
    print(f"删除的记忆: {deleted}")
    print(f"剩余记忆数量: {curve.size()}")


async def test_memory_archiver():
    """测试记忆归档（模拟）"""
    print("\n=== 测试记忆归档 ===")

    # 模拟 LLM（不做真实调用）
    class MockLLM:
        async def chat(self, messages, system, temperature, max_tokens):
            return '''{"summary_text": "在食堂和王淑芬、张志远聊天，讨论了科学话题，气氛融洽", "participants": ["王淑芬", "张志远"], "emotion": "warm", "importance_score": 0.75}'''

    mock_cloud = MockLLM()
    mock_local = MockLLM()

    archiver = MemoryArchiver(cloud_llm=mock_cloud, local_llm=mock_local, chroma_client=None)

    # 模拟对话数据
    dialogues = [
        {"from": "陈雨桐", "to": "王淑芬", "utterance": "你好呀！", "tick": 10},
        {"from": "王淑芬", "to": "陈雨桐", "utterance": "雨桐！快进食堂，刚出锅的炒蛋最香啦", "tick": 10},
        {"from": "陈雨桐", "to": "王淑芬", "utterance": "太好了！班长真暖心", "tick": 10},
        {"from": "王淑芬", "to": "陈雨桐", "utterance": "咱们快点去占座，趁热吃", "tick": 10},
    ]

    for d in dialogues:
        archiver.queue_for_archival("char_1", d)

    print(f"待归档对话数量: {archiver.get_pending_count('char_1')}")

    # 执行归档
    summary = await archiver.archive_if_needed("char_1", current_tick=20, force=True)

    if summary:
        print(f"归档成功:")
        print(f"  - memory_id: {summary.memory_id}")
        print(f"  - summary: {summary.summary_text}")
        print(f"  - emotion: {summary.emotion}")
        print(f"  - importance: {summary.importance_score:.2f}")
    else:
        print("归档失败")

    print(f"归档后待归档数量: {archiver.get_pending_count('char_1')}")


async def test_memory_retriever():
    """测试记忆检索（模拟）"""
    print("\n=== 测试记忆检索 ===")

    # 模拟 LLM
    class MockLLM:
        async def chat(self, messages, system, temperature, max_tokens):
            return '{"selected": [0, 2]}'

    mock_local = MockLLM()

    # 模拟 Chroma
    class MockCollection:
        def query(self, query_embeddings, n_results):
            return {
                "documents": [[
                    "在食堂和王淑芬聊天，她邀请我吃早餐",
                    "和张志远讨论催化反应原理",
                    "讨论了分子自组装的神奇现象"
                ]],
                "metadatas": [[
                    {"memory_id": "mem_1", "emotion": "warm", "importance": 0.8, "tick_created": 10},
                    {"memory_id": "mem_2", "emotion": "curious", "importance": 0.6, "tick_created": 15},
                    {"memory_id": "mem_3", "emotion": "curious", "importance": 0.5, "tick_created": 20},
                ]],
                "distances": [[0.2, 0.4, 0.6]],
            }

    class MockChroma:
        def get_collection(self, name):
            return MockCollection()

    retriever = MemoryRetriever(local_llm=mock_local, chroma_client=MockChroma())

    # 执行检索
    memories = await retriever.retrieve(
        agent_id="char_1",
        query_text="和王淑芬在食堂聊天",
        current_tick=25,
        neuroticism=0.5,
    )

    print(f"检索到 {len(memories)} 条记忆:")
    for mem in memories:
        print(f"  - {mem.memory_id}: {mem.content[:50]}... (score={mem.relevance_score:.3f})")

    # 测试格式化
    recall_text = retriever.format_recall_section(memories, "陈雨桐")
    print(f"\n[RECALL] 格式化结果:\n{recall_text}")


async def test_core_memory():
    """测试核心记忆保护"""
    print("\n=== 测试核心记忆保护 ===")

    curve = ForgettingCurve("char_1", neuroticism=0.5)

    # 添加普通记忆
    mem1 = MemoryEntry(
        memory_id="mem_normal",
        agent_id="char_1",
        content="今天在食堂吃饭",
        tick_created=10,
        importance=0.5,
        emotion="neutral",
    )
    curve.add_memory(mem1)

    # 添加核心记忆
    mem2 = MemoryEntry(
        memory_id="mem_core",
        agent_id="char_1",
        content="向张志远表白了我的心意",
        tick_created=10,
        importance=1.0,
        emotion="warm",
        is_core=True,
    )
    curve.add_memory(mem2)

    print("Tick 10 评分:")
    print(f"  普通记忆: {mem1.calculate_score(10, 0.5):.3f}")
    print(f"  核心记忆: {mem2.calculate_score(10, 0.5):.3f} (不应衰减)")

    print("\nTick 100 评分:")
    print(f"  普通记忆: {mem1.calculate_score(100, 0.5):.3f}")
    print(f"  核心记忆: {mem2.calculate_score(100, 0.5):.3f} (永远为1.0)")

    # 标记为核心记忆
    print("\n--- 动态标记核心记忆 ---")
    curve.mark_as_core("mem_normal")
    print(f"mem_normal 是否为核心: {curve.get_memory('mem_normal').is_core}")


async def main():
    print("=" * 60)
    print("V0.5 记忆系统测试")
    print("=" * 60)

    await test_forgetting_curve()
    await test_memory_archiver()
    await test_memory_retriever()
    await test_core_memory()

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())