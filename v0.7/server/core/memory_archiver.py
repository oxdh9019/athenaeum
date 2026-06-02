"""
memory_archiver.py — V0.7 长期记忆归档（条件反思机制）
重构：移除固定 10 Tick 触发，改为 drama_score 条件触发
定时（每10 Tick）收集对话进行摘要，存入 Chroma
支持降级到本地 JSON 文件
"""

import asyncio
import logging
import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
from utils.llm_parsing import parse_llm_json

logger = logging.getLogger(__name__)


@dataclass
class MemorySummary:
    """记忆摘要数据结构"""
    memory_id: str
    agent_id: str
    summary_text: str
    participants: list[str]
    emotion: str
    importance_score: float
    tick_created: int
    core_memory: bool = False


class MemoryArchiver:
    """
    长期记忆归档器
    - V0.7: 条件反思机制（drama_score >= 0.2 时触发）
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
        self._forgetting_curves = forgetting_curves or {}
        self._pending_archives: dict[str, list[dict]] = {}
        self._archive_collections: dict[str, any] = {}

        self._lock = asyncio.Lock()
        self._tick_counter = 0
        self._running_task: Optional[asyncio.Task] = None

        self._session_id = "default"
        self._fallback_dir = Path("./archiver_fallback")
        self._fallback_dir.mkdir(exist_ok=True)

        # V0.7: 最近对话记录（用于 drama_score 计算）
        self._recent_dialogues: dict[str, list[dict]] = {}

        # V0.7: 上次归档的 tick（防止频繁触发）
        self._last_archive_tick: dict[str, int] = {}

    def queue_for_archival(self, agent_id: str, dialogue_data: dict) -> None:
        """将对话加入待归档队列"""
        if agent_id not in self._pending_archives:
            self._pending_archives[agent_id] = []
        self._pending_archives[agent_id].append(dialogue_data)

        # V0.7: 记录最近对话用于 drama_score
        if agent_id not in self._recent_dialogues:
            self._recent_dialogues[agent_id] = []
        self._recent_dialogues[agent_id].append(dialogue_data)
        if len(self._recent_dialogues[agent_id]) > 20:
            self._recent_dialogues[agent_id] = self._recent_dialogues[agent_id][-20:]

        logger.debug(f"[Archiver] [queue_for_archival] {agent_id}: pending={len(self._pending_archives[agent_id])}")

    async def increment_tick(self, force: bool = False) -> None:
        """外部每 Tick 调用，触发归档检查"""
        self._tick_counter += 1
        if self._tick_counter % 10 == 0:
            self._running_task = asyncio.create_task(self._evaluate_and_archive())

    async def _evaluate_and_archive(self) -> None:
        """V0.7: 评估 drama_score 后再决定是否归档"""
        async with self._lock:
            agent_ids = list(self._pending_archives.keys())

        for agent_id in agent_ids:
            try:
                last_tick = self._last_archive_tick.get(agent_id, 0)
                if self._tick_counter - last_tick < 20 and len(self._pending_archives.get(agent_id, [])) < 15:
                    continue

                drama_score = self.evaluate_drama(
                    agent_id,
                    self._recent_dialogues.get(agent_id, []),
                    [],
                    []
                )

                logger.info(f"[Archiver] [{agent_id}] drama_score={drama_score:.2f}, pending={len(self._pending_archives.get(agent_id, []))}")

                if drama_score >= 0.2 or len(self._pending_archives.get(agent_id, [])) >= 15:
                    await self.archive_if_needed(agent_id, self._tick_counter, force=(drama_score >= 0.5))

            except Exception as e:
                logger.error(f"归档评估失败 {agent_id}: {e}")

    def evaluate_drama(
        self,
        agent_id: str,
        recent_dialogues: list[dict],
        relationship_changes: list,
        narrative_events: list
    ) -> float:
        """
        V0.7: 计算戏剧分数 0.0~1.0

        判断依据：
        - 对话高情绪词检测（争吵、告白等）
        - 关系变化幅度（abs(delta) > 0.2 加分）
        - 系统叙事事件（存在即加分）
        """
        score = 0.0

        high_emotion_keywords = [
            "争吵", "辩论", "冲突", "生气", "愤怒",
            "告白", "表白", "喜欢", "爱", "讨厌",
            "感谢", "感激", "道歉", "遗憾", "悲伤",
            "大笑", "惊喜", "震惊", "担心", "害怕",
        ]

        if recent_dialogues:
            high_emotion_count = 0
            total_count = len(recent_dialogues)

            for dialogue in recent_dialogues[-10:]:
                utterance = dialogue.get("utterance", "").lower()
                if any(kw in utterance for kw in high_emotion_keywords):
                    high_emotion_count += 1

            if total_count > 0:
                emotion_ratio = high_emotion_count / min(total_count, 10)
                score += min(0.4, emotion_ratio * 0.6)

        if relationship_changes:
            significant_changes = sum(1 for c in relationship_changes if abs(c) > 0.2)
            score += min(0.3, significant_changes * 0.1)

        if narrative_events:
            score += min(0.3, len(narrative_events) * 0.15)

        return min(1.0, max(0.0, score))

    async def wait_complete(self) -> None:
        """测试辅助方法"""
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
        pending = self._pending_archives.get(agent_id, [])
        logger.info(f"[Archiver] [{agent_id}] 归档检查: pending={len(pending)}, tick={current_tick}, force={force}")

        if len(pending) < 8 and not force:
            logger.info(f"[Archiver] [{agent_id}] 对话不足8条，跳过归档 (pending={len(pending)})")
            return None

        if not pending:
            return None

        dialogues = pending[:20]
        self._pending_archives[agent_id] = []
        self._last_archive_tick[agent_id] = current_tick

        logger.info(f"[Archiver] [{agent_id}] 开始归档 {len(dialogues)} 条对话")

        reflection_text = await self._generate_reflection(agent_id, dialogues)
        summary = await self._summarize_dialogues(agent_id, dialogues, current_tick, reflection_text)
        if summary:
            summary = await self._denoise_summary(summary)
            stored = await self._store_in_chroma(agent_id, summary)
            if not stored:
                await self._store_in_json_fallback(agent_id, summary)
            await self._sync_to_forgetting_curve(summary)

        return summary

    async def _generate_reflection(self, agent_id: str, dialogues: list[dict]) -> str:
        """V0.7: 生成内心感悟"""
        if len(dialogues) < 3:
            return ""

        dialogue_texts = []
        for d in dialogues[-6:]:
            speaker = d.get("from", "未知")
            utterance = d.get("utterance", "")
            dialogue_texts.append(f"{speaker}: {utterance}")

        dialogue_content = "\n".join(dialogue_texts)

        prompt = f"""作为角色 {agent_id}，请根据以下对话写出你内心的感悟和反思。
不要总结对话内容，而是表达你作为角色在这一系列交流后的内心感受。

对话：
{dialogue_content}

请用 50-80 字描述你的内心感悟，格式为一段连贯的文字：
"""

        try:
            response = await self._local.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个角色内心独白专家。直接输出感悟文字，不要其他内容。",
                temperature=0.4,
                max_tokens=200,
            )
            return response.strip()
        except Exception as e:
            logger.warning(f"[Archiver] [{agent_id}] 反思生成失败: {e}")
            return ""

    async def _summarize_dialogues(
        self,
        agent_id: str,
        dialogues: list[dict],
        current_tick: int,
        reflection: str = ""
    ) -> Optional[MemorySummary]:
        if not dialogues:
            return None

        dialogue_texts = []
        for d in dialogues:
            speaker = d.get("from", "未知")
            utterance = d.get("utterance", "")
            dialogue_texts.append(f"{speaker}: {utterance}")

        dialogue_content = "\n".join(dialogue_texts)
        reflection_hint = f"\n角色内心感悟：{reflection}" if reflection else ""

        prompt = f"""请将以下对话摘要为一条长期记忆片段：

角色ID: {agent_id}
对话记录：
{dialogue_content}
{reflection_hint}

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
            response = await self._local.chat(
                messages=[{"role": "user", "content": prompt}],
                system="你是一个记忆摘要专家。严格按JSON格式输出。",
                temperature=0.3,
                max_tokens=300,
            )

            data = parse_llm_json(response)
            if data is None:
                raise json.JSONDecodeError("无法解析 memory summary JSON", response, 0)

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
        if summary.importance_score < 0.3:
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

            text = response.strip()
            data = parse_llm_json(text)
            if data is None:
                raise json.JSONDecodeError("无法解析 noise detection JSON", text, 0)

            if data.get("is_noise", False):
                summary.importance_score = max(0.1, summary.importance_score * 0.5)
                logger.info(f"[Archiver] [{summary.agent_id}] 记忆去噪，重要性降至 {summary.importance_score:.2f}")

        except Exception as e:
            logger.warning(f"[Archiver] [{summary.agent_id}] 去噪失败: {e}")

        return summary

    async def _store_in_chroma(self, agent_id: str, summary: MemorySummary) -> bool:
        if self._chroma is None:
            logger.warning(f"[Archiver] [{agent_id}] Chroma 未初始化，跳过存储")
            return False

        collection_name = f"{self._session_id}_{agent_id}_longterm"

        # 必须持锁：collection 重建期间，如果 retriever 并发 query，
        # 会拿到 None 然后 _generate_embedding 失败，整个 collection 记忆丢失。
        async with self._lock:
            try:
                if collection_name not in self._archive_collections:
                    self._archive_collections[collection_name] = self._chroma.get_or_create_collection(
                        name=collection_name,
                        metadata={"agent_id": agent_id}
                    )

                collection = self._archive_collections[collection_name]

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
                    if "dimension" in str(add_error).lower() or "expected embedding" in str(add_error).lower():
                        logger.warning(f"[Archiver] [{agent_id}] 集合维度不匹配，删除并重建")
                        self._chroma.delete_collection(collection_name)
                        self._archive_collections.pop(collection_name, None)
                        self._archive_collections[collection_name] = self._chroma.get_or_create_collection(
                            name=collection_name,
                            metadata={"agent_id": agent_id, "embedding_dimensions": 1024}
                        )
                        collection = self._archive_collections[collection_name]
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
        session_dir = self._fallback_dir / self._session_id
        session_dir.mkdir(exist_ok=True)
        fallback_path = session_dir / f"{agent_id}_{summary.tick_created}.json"
        try:
            data = asdict(summary)
            with open(fallback_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[Archiver] [{agent_id}] 记忆已降级存入 JSON: {fallback_path}")
            # 清理该 agent 的旧 JSON 备份（每个 agent 最多保留 50 个）
            await self._prune_json_fallback(session_dir, agent_id, keep=50)
        except Exception as e:
            logger.error(f"[Archiver] [{agent_id}] JSON 降级存储失败: {e}")

    async def _prune_json_fallback(self, session_dir, agent_id: str, keep: int = 50) -> None:
        """
        每个 agent 在 session_dir 下最多保留 `keep` 个 JSON 备份。
        多余的按文件名（tick）升序删除最早的。retriever 反正只读最新 N，
        这里给个 cap 防止多周使用后磁盘涨满。
        """
        try:
            files = sorted(session_dir.glob(f"{agent_id}_*.json"))
            excess = len(files) - keep
            if excess > 0:
                for old in files[:excess]:
                    old.unlink(missing_ok=True)
                logger.info(f"[Archiver] [{agent_id}] 清理了 {excess} 个旧 JSON 备份")
        except Exception as e:
            logger.warning(f"[Archiver] [{agent_id}] JSON 备份清理失败: {e}")

    async def _sync_to_forgetting_curve(self, summary: MemorySummary):
        logger.info(f"[Archiver] [_sync_to_forgetting_curve] called: agent={summary.agent_id}, memory_id={summary.memory_id}")

        if not summary or self._forgetting_curves is None:
            return

        try:
            from core.forgetting_curve import MemoryEntry, ForgettingCurve

            agent_id = summary.agent_id

            if agent_id not in self._forgetting_curves:
                self._forgetting_curves[agent_id] = ForgettingCurve(agent_id)

            curve = self._forgetting_curves[agent_id]

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
        return len(self._pending_archives.get(agent_id, []))

    def set_session_id(self, session_id: str) -> None:
        self._session_id = session_id
        self._archive_collections.clear()
        logger.info(f"[Archiver] 会话 ID 已更新: {session_id}")