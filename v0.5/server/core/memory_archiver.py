"""
memory_archiver.py — V0.5 长期记忆归档
定时（每10 Tick）收集对话进行摘要，存入 Chroma
支持降级到本地 JSON 文件
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MemorySummary:
    """记忆摘要数据结构"""
    memory_id: str
    agent_id: str
    summary_text: str
    participants: list[str]  # 涉及的 Agent ID 列表
    emotion: str  # 情感基调
    importance_score: float  # 重要性 0.0-1.0
    tick_created: int
    core_memory: bool = False  # 是否为核心记忆


class MemoryArchiver:
    """
    长期记忆归档器
    - 定时（每10 Tick）收集待归档对话
    - 使用本地 Ollama 进行摘要
    - 本地 Qwen 做去噪处理
    - 结果存入 Chroma 集合 `agent_{id}_longterm`
    - Chroma 不可用时降级到本地 JSON 文件
    """

    def __init__(self, cloud_llm, local_llm, chroma_client=None, forgetting_curves=None):
        self._cloud = cloud_llm
        self._local = local_llm
        self._chroma = chroma_client
        self._forgetting_curves = forgetting_curves or {}  # agent_id -> ForgettingCurve
        self._pending_archives: dict[str, list[dict]] = {}  # agent_id -> 待归档对话列表
        self._archive_collections: dict[str, any] = {}  # agent_id -> Chroma 集合

        # 并发安全
        self._lock = asyncio.Lock()
        self._tick_counter = 0
        self._running_task: Optional[asyncio.Task] = None

        # V0.7: 世界会话 ID（用于数据隔离）
        self._session_id = "default"

        # 降级文件目录
        self._fallback_dir = Path("./archiver_fallback")
        self._fallback_dir.mkdir(exist_ok=True)

    def queue_for_archival(self, agent_id: str, dialogue_data: dict) -> None:
        """
        将对话加入待归档队列
        dialogue_data: {"from": str, "to": str, "utterance": str, "tick": int}
        """
        if agent_id not in self._pending_archives:
            self._pending_archives[agent_id] = []
        self._pending_archives[agent_id].append(dialogue_data)
        logger.debug(f"[Archiver] [queue_for_archival] {agent_id}: pending_count={len(self._pending_archives[agent_id])}")

    async def increment_tick(self, force: bool = False) -> None:
        """
        外部每 Tick 调用，触发归档检查
        force 参数用于手动触发归档测试
        """
        self._tick_counter += 1
        if force or self._tick_counter % 10 == 0:
            self._running_task = asyncio.create_task(self._archive_all_agents())

    async def wait_complete(self) -> None:
        """测试辅助方法，等待所有归档任务完成"""
        if self._running_task and not self._running_task.done():
            await self._running_task

    async def _archive_all_agents(self) -> None:
        async with self._lock:
            agent_ids = list(self._pending_archives.keys())
        for agent_id in agent_ids:
            try:
                await self.archive_if_needed(agent_id, self._tick_counter)
            except Exception as e:
                logger.error(f"归档失败 {agent_id}: {e}")

    async def archive_if_needed(self, agent_id: str, current_tick: int, force: bool = False) -> Optional[MemorySummary]:
        """
        检查是否需要归档，如果队列积累足够则执行归档

        Args:
            agent_id: Agent ID
            current_tick: 当前 tick
            force: 是否强制归档（即使不足10条）

        Returns:
            MemorySummary 或 None
        """
        pending = self._pending_archives.get(agent_id, [])
        logger.info(f"[Archiver] [{agent_id}] 归档检查: pending={len(pending)}, tick={current_tick}, force={force}")
        if len(pending) < 10 and not force:
            logger.info(f"[Archiver] [{agent_id}] 对话不足10条，跳过归档 (pending={len(pending)})")
            return None

        if not pending:
            return None

        # 执行归档
        dialogues = pending[:20]  # 最多归档20条
        self._pending_archives[agent_id] = []
        logger.info(f"[Archiver] [{agent_id}] 开始归档 {len(dialogues)} 条对话")

        summary = await self._summarize_dialogues(agent_id, dialogues, current_tick)
        if summary:
            # 去噪处理
            summary = await self._denoise_summary(summary)
            # 存入 Chroma，降级到 JSON
            stored = await self._store_in_chroma(agent_id, summary)
            if not stored:
                # Chroma 失败，降级到 JSON
                await self._store_in_json_fallback(agent_id, summary)
            # V0.5: 同步写入 ForgettingCurve
            await self._sync_to_forgetting_curve(summary)

        return summary

    async def _summarize_dialogues(self, agent_id: str, dialogues: list[dict], current_tick: int) -> Optional[MemorySummary]:
        """
        使用本地 Ollama 对对话进行摘要
        """
        if not dialogues:
            return None

        # 构建对话文本
        dialogue_texts = []
        for d in dialogues:
            speaker = d.get("from", "未知")
            utterance = d.get("utterance", "")
            dialogue_texts.append(f"{speaker}: {utterance}")

        dialogue_content = "\n".join(dialogue_texts)

        prompt = f"""请将以下对话摘要为一条长期记忆片段：

角色ID: {agent_id}
对话记录：
{dialogue_content}

请严格按以下JSON格式输出（不要输出任何其他内容）：
{{
  "summary_text": "摘要内容（50-100字，包含对话的核心信息和意义）",
  "participants": ["涉及的对方角色ID列表"],
  "emotion": "情感基调（warm/curious/neutral/wary/anxious）",
  "importance_score": 0.0到1.0之间的小数
}}

摘要要求：
- 突出对话中的重要交互和情感变化
- 忽略纯粹的客套话（如"好的"、"嗯"）
- 关注引发关系变化或深入交流的内容"""

        try:
            # V0.5: 使用本地 Ollama（qwen3.5:4b）进行摘要
            response = await self._local.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个记忆摘要专家。严格按JSON格式输出。",
                temperature=0.3,
                max_tokens=300,
            )

            import json
            import re

            # 提取 JSON
            text = response.strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                data = json.loads(text)

            participants = data.get("participants", [])
            if isinstance(participants, str):
                participants = [participants]

            memory_id = f"mem_{agent_id}_{current_tick}_{len(dialogues)}"

            summary = MemorySummary(
                memory_id=memory_id,
                agent_id=agent_id,
                summary_text=data.get("summary_text", ""),
                participants=participants,
                emotion=data.get("emotion", "neutral"),
                importance_score=float(data.get("importance_score", 0.5)),
                tick_created=current_tick,
            )

            logger.info(f"[Archiver] [{agent_id}] 归档成功: {summary.summary_text[:50]}..., importance={summary.importance_score:.2f}")
            return summary

        except Exception as e:
            logger.error(f"[Archiver] [{agent_id}] 摘要失败: {e}")
            return None

    async def _denoise_summary(self, summary: MemorySummary) -> MemorySummary:
        """
        本地 Qwen 对归档后的记忆做快速去噪
        删除与角色身份完全无关的噪音记忆
        """
        if summary.importance_score < 0.3:
            # 重要性太低的记忆直接返回（跳过去噪）
            return summary

        prompt = f"""请判断以下记忆是否与角色身份相关：

角色ID: {summary.agent_id}
记忆内容: {summary.summary_text}

如果记忆内容纯粹是客套话、无关闲聊或噪音（如"你好"、"再见"、"嗯好的"），请返回：
{{"is_noise": true}}

如果记忆内容与角色有关（涉及角色身份、性格、关系），请返回：
{{"is_noise": false}}

只输出JSON。"""

        try:
            response = await self._local.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个记忆分析助手。",
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

            if data.get("is_noise", False):
                # 噪音记忆，重要性降低
                summary.importance_score = max(0.1, summary.importance_score * 0.5)
                logger.info(f"[Archiver] [{summary.agent_id}] 记忆去噪，重要性降至 {summary.importance_score:.2f}")

        except Exception as e:
            logger.warning(f"[Archiver] [{summary.agent_id}] 去噪失败: {e}")

        return summary

    async def _store_in_chroma(self, agent_id: str, summary: MemorySummary) -> bool:
        """
        归档结果存入 Chroma 集合 `session_agent_{id}_longterm`
        V0.7: 使用 session_id 前缀实现数据隔离
        返回是否成功
        """
        if self._chroma is None:
            logger.warning(f"[Archiver] [{agent_id}] Chroma 未初始化，跳过存储")
            return False

        collection_name = f"{self._session_id}_{agent_id}_longterm"

        try:
            # 获取或创建集合（惰性创建）
            if collection_name not in self._archive_collections:
                self._archive_collections[collection_name] = self._chroma.get_or_create_collection(
                    name=collection_name,
                    metadata={"agent_id": agent_id}
                )

            collection = self._archive_collections[collection_name]

            # 添加记忆（使用 summary_text 作为 document，metadata 存储额外信息）
            try:
                collection.add(
                    documents=[summary.summary_text],
                    metadatas=[{
                        "memory_id": summary.memory_id,
                        "agent_id": summary.agent_id,
                        "emotion": summary.emotion,
                        "importance": summary.importance_score,
                        "tick_created": summary.tick_created,
                        "is_core": summary.core_memory,
                        "participants": ",".join(summary.participants),
                    }],
                    ids=[summary.memory_id]
                )
            except Exception as add_error:
                # 如果是维度不匹配错误，删除集合并重建
                if "dimension" in str(add_error).lower() or "expected embedding" in str(add_error).lower():
                    logger.warning(f"[Archiver] [{agent_id}] 集合维度不匹配，删除并重建")
                    self._chroma.delete_collection(collection_name)
                    del self._archive_collections[collection_name]
                    self._archive_collections[collection_name] = self._chroma.get_or_create_collection(
                        name=collection_name,
                        metadata={"agent_id": agent_id, "embedding_dimensions": 1024}
                    )
                    collection = self._archive_collections[collection_name]
                    # 重试添加
                    collection.add(
                        documents=[summary.summary_text],
                        metadatas=[{
                            "memory_id": summary.memory_id,
                            "agent_id": summary.agent_id,
                            "emotion": summary.emotion,
                            "importance": summary.importance_score,
                            "tick_created": summary.tick_created,
                            "is_core": summary.core_memory,
                            "participants": ",".join(summary.participants),
                        }],
                        ids=[summary.memory_id]
                    )
                else:
                    raise add_error

            logger.info(f"[Archiver] [{agent_id}] 记忆已存入 Chroma: {collection_name}/{summary.memory_id}")
            return True

        except Exception as e:
            logger.error(f"[Archiver] [{agent_id}] Chroma 存储失败: {e}")
            return False

    async def _store_in_json_fallback(self, agent_id: str, summary: MemorySummary) -> None:
        """
        Chroma 不可用时的降级存储：存入本地 JSON 文件
        V0.7: 使用 session_id 子目录实现隔离
        """
        # V0.7: 使用 session_id 子目录
        session_dir = self._fallback_dir / self._session_id
        session_dir.mkdir(exist_ok=True)
        fallback_path = session_dir / f"{agent_id}_{summary.tick_created}.json"
        try:
            data = asdict(summary)
            with open(fallback_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[Archiver] [{agent_id}] 记忆已降级存入 JSON: {fallback_path}")
        except Exception as e:
            logger.error(f"[Archiver] [{agent_id}] JSON 降级存储失败: {e}")

    async def _sync_to_forgetting_curve(self, summary: MemorySummary):
        """
        V0.5: 同步归档数据到 ForgettingCurve（内存）
        这样日记 API 可以读取到记忆
        """
        logger.info(f"[Archiver] [_sync_to_forgetting_curve] called: agent={summary.agent_id}, memory_id={summary.memory_id}, _forgetting_curves={list(self._forgetting_curves.keys())}")
        if not summary or self._forgetting_curves is None:
            logger.warning(f"[Archiver] [_sync_to_forgetting_curve] early return: summary={summary is not None}, _forgetting_curves={self._forgetting_curves is not None}")
            return

        try:
            # 延迟导入避免循环依赖
            from core.forgetting_curve import MemoryEntry, ForgettingCurve

            agent_id = summary.agent_id

            # 获取或创建 ForgettingCurve
            if agent_id not in self._forgetting_curves:
                self._forgetting_curves[agent_id] = ForgettingCurve(agent_id)

            curve = self._forgetting_curves[agent_id]

            # 创建记忆条目
            entry = MemoryEntry(
                memory_id=summary.memory_id,
                agent_id=agent_id,
                content=summary.summary_text,
                tick_created=summary.tick_created,
                importance=summary.importance_score,
                emotion=summary.emotion,
                is_core=summary.core_memory,
                context=f"participants: {summary.participants}",
            )

            curve.add_memory(entry)
            logger.info(f"[Archiver] [{agent_id}] 记忆已同步到 ForgettingCurve: {summary.memory_id}")

        except Exception as e:
            logger.warning(f"[Archiver] [{summary.agent_id}] 同步到 ForgettingCurve 失败: {e}")

    def get_pending_count(self, agent_id: str) -> int:
        """获取待归档数量"""
        return len(self._pending_archives.get(agent_id, []))

    def set_session_id(self, session_id: str) -> None:
        """
        V0.7: 设置世界会话 ID（用于数据隔离）
        每次 reset_world 时调用，生成新的 collection
        """
        self._session_id = session_id
        # 清除旧的 collection 缓存，强制使用新的 collection
        self._archive_collections.clear()
        logger.info(f"[Archiver] 会话 ID 已更新: {session_id}")