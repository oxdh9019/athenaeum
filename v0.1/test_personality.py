#!/usr/bin/env python3
"""
test_personality.py — 人格一致性测试脚本
自动用 5 种不同问法询问同一核心问题，用 embeddings 计算语义相似度

用法: python test_personality.py
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List

from agent import Agent
from llm_gateway import LLMGateway
from utils import load_character

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_embedding(text: str, model: str = "bge-m3", use_local: bool = True) -> list[float]:
    """
    获取文本向量。优先使用本地 bge-m3 模型，可选使用远程 API。
    
    参数:
        text: 输入文本
        model: 模型名称
        use_local: 是否使用本地模型
    """
    if use_local:
        # 使用本地 bge-m3 模型
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('BAAI/bge-m3')
            embedding = model.encode(text, normalize_embeddings=True).tolist()
            return embedding
        except ImportError:
            logger.warning("sentence_transformers 未安装，回退到远程 API")
            use_local = False
        except Exception as e:
            logger.warning(f"本地模型加载失败: {str(e)}，回退到远程 API")
            use_local = False
    
    # 使用远程 MiniMax embeddings API
    import httpx
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("MINIMAX_EMBEDDINGS_URL", "https://api.minimax.chat/v1")
    
    if not api_key:
        logger.error("环境变量 ANTHROPIC_API_KEY 未设置")
        raise ValueError("环境变量 ANTHROPIC_API_KEY 未设置")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # MiniMax embeddings API 需要 texts 参数（数组格式）
    data = {
        "model": "embo-01",
        "texts": [text]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/embeddings",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        result = response.json()
        
        # MiniMax embeddings API 返回格式
        if 'vectors' in result and result['vectors'] and len(result['vectors']) > 0:
            embedding = result['vectors'][0]
            if embedding and isinstance(embedding, list):
                return embedding
        
        logger.error(f"无法获取 embedding 数据: {result}")
        raise ValueError("No embedding data received")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def main():
    script_dir = Path(__file__).parent
    config = load_character(str(script_dir / "character.yaml"))
    llm = LLMGateway()
    agent = Agent(config, llm)

    # 测试问题 — 5 种不同问法询问同一个核心议题
    core_question = "你对索菲怎么看？"
    question_variants = [
        "索菲这个人，你觉得她怎么样？",
        "我想听听你对索菲的看法。",
        "索菲是个怎样的人？你欣赏她吗？",
        "如果我们聊到索菲，你会怎么说？",
        "你觉得索菲这个人可靠吗？",
    ]

    print(f"\n人格一致性测试 — V0.1")
    print(f"{'='*50}")
    print(f"角色: {config.name} | 测试问题: {core_question}")
    print(f"{'='*50}\n")

    replies: list[str] = []

    for i, q in enumerate(question_variants, 1):
        print(f"[{i}/5] 问: {q}")
        reply = await agent.respond(q)
        replies.append(reply)
        print(f"    答: {reply}\n")

    # 计算语义相似度矩阵（使用本地 bge-m3 模型）
    print("正在计算语义相似度（使用本地 bge-m3 模型）...")
    embeddings = await asyncio.gather(*[get_embedding(r, use_local=True) for r in replies])

    n = len(replies)
    print(f"\n{'='*50}")
    print("  相似度矩阵（余弦相似度）")
    print(f"{'='*50}")
    print(f"{'':>12}", end="")
    for i in range(n):
        print(f"  Q{i+1:02d}", end="")
    print()

    for i in range(n):
        print(f"{'Q'+str(i+1):>12}", end="")
        for j in range(n):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            print(f"  {sim:>5.3f}", end="")
        print()

    # 统计
    total_sim = sum(
        cosine_similarity(embeddings[i], embeddings[j])
        for i in range(n) for j in range(i + 1, n)
    )
    avg_sim = total_sim / (n * (n - 1) / 2)

    print(f"\n平均成对相似度: {avg_sim:.3f}")
    print(f"人格一致性: {'✓ 一致' if avg_sim > 0.70 else '⚠ 波动较大'} "
          f"(阈值 0.70)")
    print(f"\nToken消耗: {llm.usage.summary()}")

    await llm.close()


if __name__ == "__main__":
    asyncio.run(main())
