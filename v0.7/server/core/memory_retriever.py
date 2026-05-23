"""
memory_retriever.py — V0.5 语义检索
使用本地 bge-m3 生成 embedding，在 Chroma 中检索 Top-5，本地 Qwen 重排序选出 Top-3
V0.7: 支持 JSON fallback 回读（当 Chroma 不可用时）
"""

import logging
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievedMemory:
    """检索到的记忆"""
    memory_id: str
    content: str
    agent_id: str
    emotion: str
    importance: float
    relevance_score: float
    tick_created: int


class MemoryRetriever:
    """
    语义检索器
    - 使用本地 bge-m3 生成 embedding
    - 在 Chroma 中检索 Top-5
    - 本地 Qwen 重排序选出 Top-3
    - 结果注入 Agent 的 Prompt（[RECALL] 标签内）
    - 不缓存 Chroma 集合，直接获取由客户端管理连接
    """

    def __init__(self, local_llm, chroma_client=None, embedder=None):
        """
        Args:
            local_llm: 本地 Qwen（用于重排序）
            chroma_client: Chroma 客户端
            embedder: embedding 生成器（bge-m3），如果没有则用 local_llm
        """
        self._local = local_llm
        self._chroma = chroma_client
        self._embedder = embedder or local_llm  # 如果没有专门的 embedder，用 local_llm
        # V0.7: 世界会话 ID（用于数据隔离）
        self._session_id = "default"
        # V0.7: JSON fallback 目录（与 archiver 相同路径）
        self._fallback_dir = Path("./archiver_fallback")

    async def retrieve(
        self,
        agent_id: str,
        query_text: str,
        current_tick: int,
        neuroticism: float = 0.5,
        top_k: int = 5,
        final_top: int = 3,
    ) -> list[RetrievedMemory]:
        """
        检索与当前上下文相关的记忆

        Args:
            agent_id: Agent ID
            query_text: 当前意图的 reasoning 文本或对话上下文
            current_tick: 当前 tick（用于计算遗忘衰减）
            neuroticism: 角色神经质（用于遗忘曲线计算）
            top_k: 初始检索数量
            final_top: 最终返回数量

        Returns:
            Top-3 检索结果
        """
        if self._chroma is None:
            logger.warning(f"[Retriever] [{agent_id}] Chroma 未初始化，无法检索")
            return []

        collection_name = f"{self._session_id}_{agent_id}_longterm"

        try:
            # 直接获取集合，不缓存，由 Chroma 客户端管理连接
            try:
                collection = self._chroma.get_collection(name=collection_name)
            except Exception:
                logger.info(f"[Retriever] [{agent_id}] 集合 {collection_name} 不存在")
                return []

            # 生成 query embedding
            query_embedding = await self._generate_embedding(query_text)
            if not query_embedding:
                logger.warning(f"[Retriever] [{agent_id}] embedding 生成失败")
                return []

            # Chroma 检索 Top-5
            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                )
            except Exception as query_error:
                # 维度不匹配错误：删除集合，下次检索时会重建
                if "dimension" in str(query_error).lower() or "expecting" in str(query_error).lower():
                    logger.warning(f"[Retriever] [{agent_id}] 集合维度不匹配，删除并重建: {query_error}")
                    try:
                        self._chroma.delete_collection(collection_name)
                    except Exception:
                        pass
                    return []
                raise query_error

            if not results or not results.get("documents"):
                return []

            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results.get("distances", [[1.0] * len(documents)])[0]

            # 构建候选记忆列表
            candidates = []
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
                # 计算相似度分数（1 - distance）
                similarity = 1.0 - min(dist, 1.0)

                # 计算遗忘衰减
                tick_created = meta.get("tick_created", 0)
                delta_t = current_tick - tick_created
                lambda_base = 0.03
                lambda_value = lambda_base + (0.5 - neuroticism) * 0.04
                decay = __import__('math').exp(-lambda_value * delta_t)

                importance = meta.get("importance", 0.5)
                # 综合评分 = 相似度 * 重要性 * 衰减
                combined_score = similarity * importance * decay

                candidates.append(RetrievedMemory(
                    memory_id=meta.get("memory_id", f"unknown_{i}"),
                    content=doc,
                    agent_id=agent_id,
                    emotion=meta.get("emotion", "neutral"),
                    importance=importance,
                    relevance_score=combined_score,
                    tick_created=tick_created,
                ))

            # 本地 Qwen 重排序
            reranked = await self._rerank_candidates(query_text, candidates)

            # 返回 Top-3
            return reranked[:final_top]

        except Exception as e:
            logger.error(f"[Retriever] [{agent_id}] 检索失败: {e}")
            return []

    async def _generate_embedding(self, text: str) -> Optional[list[float]]:
        """
        使用 bge-m3 生成文本 embedding
        如果没有专门的 embedder，使用 local_llm 的 embedding 方法
        """
        try:
            # 尝试使用 embedder
            if hasattr(self._embedder, 'generate_embedding'):
                return await self._embedder.generate_embedding(text)
            elif hasattr(self._embedder, 'embed'):
                # embed() 期望 list[str]，传入单条文本需包装成列表
                embeddings = await self._embedder.embed([text])
                return embeddings[0] if embeddings else None
            else:
                # 如果没有专门的 embedding 方法，返回 None
                logger.warning(f"[Retriever] embedder 没有 embedding 方法")
                return None
        except Exception as e:
            logger.error(f"[Retriever] embedding 生成失败: {e}")
            return None

    async def _rerank_candidates(
        self,
        query: str,
        candidates: list[RetrievedMemory]
    ) -> list[RetrievedMemory]:
        """
        本地 Qwen 对检索结果进行重排序
        基于相关性和遗忘曲线分数选出最终 Top-3
        """
        if not candidates:
            return []

        prompt = f"""请对以下记忆进行重排序，选出与查询最相关的记忆。

查询: {query}

候选记忆:
"""

        for i, mem in enumerate(candidates):
            prompt += f"{i+1}. [{mem.emotion}] {mem.content[:100]}... (相关性: {mem.relevance_score:.2f})\n"

        prompt += """
请根据与查询的相关性，挑选出最相关的3条记忆。
输出JSON格式：
{"selected": [0, 2, 4]}  // 选中记忆的索引列表

只输出JSON，不要其他内容。"""

        try:
            response = await self._local.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个记忆检索助手。严格按JSON格式输出。",
                temperature=0.1,
                max_tokens=100,
            )

            import json
            import re

            text = response.strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                data = json.loads(text)

            selected_indices = data.get("selected", [])
            if not selected_indices or len(selected_indices) == 0:
                # 如果解析失败，按综合分数排序返回
                return sorted(candidates, key=lambda m: m.relevance_score, reverse=True)[:3]

            # 根据索引选择记忆
            selected = [candidates[i] for i in selected_indices if i < len(candidates)]

            # 如果选中的不足3条，补充其他高分记忆
            if len(selected) < 3:
                other_indices = set(range(len(candidates))) - set(selected_indices)
                for idx in sorted(other_indices, key=lambda i: candidates[i].relevance_score, reverse=True):
                    if len(selected) >= 3:
                        break
                    if candidates[idx] not in selected:
                        selected.append(candidates[idx])

            return selected[:3]

        except Exception as e:
            logger.warning(f"[Retriever] 重排序失败: {e}")
            # 降级：按综合分数排序
            return sorted(candidates, key=lambda m: m.relevance_score, reverse=True)[:3]

    def format_recall_section(self, memories: list[RetrievedMemory], agent_name: str) -> str:
        """
        将检索结果格式化为 [RECALL] 标签内的内容
        """
        if not memories:
            return ""

        recall_text = f"\n[RECALL] {agent_name} 想起了过去的记忆：\n"
        for mem in memories:
            recall_text += f"- {mem.content}"
            if mem.emotion != "neutral":
                recall_text += f"（情感基调：{mem.emotion}）"
            recall_text += "\n"
        recall_text += "[/RECALL]"

        return recall_text

    def set_session_id(self, session_id: str) -> None:
        """V0.7: 设置世界会话 ID（用于数据隔离）"""
        self._session_id = session_id
        logger.info(f"[Retriever] 会话 ID 已更新: {session_id}")

    async def retrieve_by_agent(self, agent_id: str, max_count: int = 100) -> list:
        """
        V0.7: 根据 agent_id 读取该角色的所有记忆（用于日记 API）
        优先级：1. Chroma  2. JSON fallback（跨服恢复）
        返回 MemoryEntry 对象列表，供 journal API 合并使用
        """
        from core.forgetting_curve import MemoryEntry

        entries = []

        # 1. 先尝试从 Chroma 读取
        if self._chroma is not None:
            collection_name = f"{self._session_id}_{agent_id}_longterm"
            try:
                collection = self._chroma.get_collection(name=collection_name)
                results = collection.get()
                if results and results.get("documents"):
                    documents = results.get("documents", [])
                    metadatas = results.get("metadatas", [])
                    for doc, meta in zip(documents, metadatas):
                        entry = MemoryEntry(
                            memory_id=meta.get("memory_id", "unknown"),
                            agent_id=agent_id,
                            content=doc,
                            tick_created=meta.get("tick_created", 0),
                            importance=float(meta.get("importance", 0.5)),
                            emotion=meta.get("emotion", "neutral"),
                            is_core=meta.get("is_core", False),
                            context=f"participants: {meta.get('participants', '')}",
                        )
                        entries.append(entry)
                    logger.info(f"[Retriever] [{agent_id}] 从 Chroma 读取 {len(entries)} 条记忆")
                    return entries
            except Exception as e:
                logger.warning(f"[Retriever] [{agent_id}] Chroma 读取失败: {e}")

        # 2. Chroma 没有或失败，从 JSON fallback 读取（跨服恢复）
        # V0.7: 只读 session 子目录（已隔离），不读根目录（未隔离）
        session_dir = self._fallback_dir / self._session_id
        if not session_dir.exists():
            logger.info(f"[Retriever] [{agent_id}] session={self._session_id} 无 JSON fallback（目录不存在）")
            return []

        json_files = sorted(session_dir.glob(f"{agent_id}_*.json"))

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                entry = MemoryEntry(
                    memory_id=data.get("memory_id", json_file.stem),
                    agent_id=agent_id,
                    content=data.get("summary_text", ""),
                    tick_created=data.get("tick_created", 0),
                    importance=float(data.get("importance_score", 0.5)),
                    emotion=data.get("emotion", "neutral"),
                    is_core=data.get("core_memory", False),
                    context=f"participants: {data.get('participants', [])}",
                )
                entries.append(entry)
            except Exception as e:
                logger.warning(f"[Retriever] [{agent_id}] 读取 JSON 失败 {json_file}: {e}")

        logger.info(f"[Retriever] [{agent_id}] 从 JSON fallback 读取 {len(entries)} 条记忆")
        return entries

    async def list_entries(self, agent_id: str, offset: int = 0, limit: int = 10) -> list[dict]:
        """
        列出记忆条目（用于 Diary API）
        不进行语义检索，直接返回已排序的记忆列表
        """
        if self._chroma is None:
            logger.warning(f"[Retriever] [{agent_id}] Chroma 未初始化")
            return []

        collection_name = f"{self._session_id}_{agent_id}_longterm"

        try:
            collection = self._chroma.get_collection(name=collection_name)
            # 获取所有记忆（按 tick_created 倒序）
            results = collection.get()
            if not results or not results.get("documents"):
                return []

            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])

            # 构建条目列表
            entries = []
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                entries.append({
                    "summary": doc,
                    "emotion": meta.get("emotion", "neutral"),
                    "importance": meta.get("importance", 0.5),
                    "tick": meta.get("tick_created", 0),
                    "memory_id": meta.get("memory_id", f"unknown_{i}"),
                    "participants": meta.get("participants", "").split(",") if meta.get("participants") else [],
                })

            # 按 tick 倒序
            entries.sort(key=lambda e: e["tick"], reverse=True)

            # 分页
            return entries[offset:offset + limit]

        except Exception as e:
            logger.error(f"[Retriever] [{agent_id}] list_entries 失败: {e}")
            return []