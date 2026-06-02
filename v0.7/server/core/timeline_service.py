"""
timeline_service.py — V0.7 Phase B Step 2

统一对外暴露时间线和角色日记的查询层。
- /world/timeline: 聚合 _recent_dialogues (live) + _recent_actions (live)
- /agent/{id}/journal: 优先读 MemoryArchiver 归档 (archiver_fallback/*.json),
  没有任何归档时,回退到该 agent 参与的最近对话合成"近期条目"。

设计取舍:
- 字段映射在服务端做,前端拿到的形状稳定,无需关心后端 MemorySummary 命名
  (summary_text → content, importance_score → importance, core_memory → is_core)
- pagination 用 page+size,内部转 offset = (page-1) * size
- 读路径,不修改任何世界状态;不持锁
- 错误隔离:任何数据源读取失败返回空列表,不让单点失败影响其他源
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# 列表端点允许的最大 size,防止误用 ?size=1000000 把服务端拉爆
MAX_PAGE_SIZE = 200


def _clamp_page(page: Optional[int], size: Optional[int], default_size: int = 20) -> tuple[int, int]:
    """Normalize page/size query params: page>=1, 1<=size<=MAX_PAGE_SIZE."""
    try:
        p = int(page) if page is not None else 1
    except (TypeError, ValueError):
        p = 1
    try:
        s = int(size) if size is not None else default_size
    except (TypeError, ValueError):
        s = default_size
    if p < 1:
        p = 1
    if s < 1:
        s = 1
    if s > MAX_PAGE_SIZE:
        s = MAX_PAGE_SIZE
    return p, s


class TimelineService:
    """
    Aggregates world state and archiver for query-side timeline / journal.

    不要直接构造;应通过 `get_timeline_service()` 或 AppState.timeline_service 拿。
    """

    def __init__(self, world, memory_archiver=None, fallback_dir: Path = None):
        self._world = world
        self._archiver = memory_archiver
        # 与 memory_archiver / memory_retriever 共享同一目录
        self._fallback_dir = fallback_dir or Path("./archiver_fallback")

    # ============== /world/timeline ==============

    def query_timeline(
        self,
        event_type: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        聚合 _recent_dialogues 和 _recent_actions,按 tick 倒序,分页返回。

        Returns:
            { "events": [...], "total": int, "page": int, "size": int }
        """
        p, s = _clamp_page(page, size, default_size=20)
        events: list[dict] = []

        # 1) live dialogues
        for d in self._safe_recent_dialogues():
            utterance = d.get("utterance", "") or ""
            micro = d.get("micro_action")
            desc = utterance
            if micro:
                desc = f"{micro}\n{utterance}" if utterance else micro
            events.append({
                "id": f"dlg_{d.get('tick', 0)}_{d.get('from_id', '')}_{d.get('to', '')}",
                "event_type": "dialogue",
                "description": desc,
                "participants": [
                    p_id for p_id in (d.get("from_id"), d.get("to"))
                    if p_id
                ],
                "tick": int(d.get("tick", 0) or 0),
            })

        # 2) live actions
        for a in self._safe_recent_actions():
            events.append({
                "id": f"act_{a.get('tick', 0)}_{a.get('agent_id', '')}",
                "event_type": "action",
                "description": a.get("description") or a.get("action") or "",
                "participants": [a["agent_id"]] if a.get("agent_id") else [],
                "tick": int(a.get("tick", 0) or 0),
            })

        # 3) filter
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        # 4) sort tick desc
        events.sort(key=lambda e: e["tick"], reverse=True)

        total = len(events)
        offset = (p - 1) * s
        return {
            "events": events[offset:offset + s],
            "total": total,
            "page": p,
            "size": s,
        }

    # ============== /agent/{id}/journal ==============

    def query_journal(
        self,
        agent_id: str,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        优先从 MemoryArchiver 归档(archiver_fallback/{session}/{agent}_*.json)读;
        如果该 agent 还没有触发过归档 (pending < 8),
        回退到该 agent 参与的最近对话,合成条目返回。

        字段映射(后端 MemorySummary/dataclass → 前端 Memory interface):
            summary_text      -> content
            importance_score  -> importance
            core_memory       -> is_core
            participants      -> context (", ".join)
        """
        p, s = _clamp_page(page, size, default_size=10)

        memories: list[dict] = []
        source = "empty"

        archived = self._load_archived_memories(agent_id)
        if archived:
            memories = archived
            source = "archive"
        else:
            synthesized = self._synthesize_from_recent(agent_id)
            if synthesized:
                memories = synthesized
                source = "synthesized"

        # sort tick_created desc
        memories.sort(key=lambda m: m["tick_created"], reverse=True)

        total = len(memories)
        offset = (p - 1) * s
        return {
            "memories": memories[offset:offset + s],
            "total": total,
            "page": p,
            "size": s,
            "source": source,
        }

    # ============== 内部辅助 ==============

    def _safe_recent_dialogues(self) -> list[dict]:
        try:
            w = self._world
            if w is None:
                return []
            return list(getattr(w, "_recent_dialogues", []) or [])
        except Exception as e:
            logger.warning(f"[timeline] 读 _recent_dialogues 失败: {e}")
            return []

    def _safe_recent_actions(self) -> list:
        try:
            w = self._world
            if w is None:
                return []
            # deque 也可 iter
            return list(getattr(w, "_recent_actions", []) or [])
        except Exception as e:
            logger.warning(f"[timeline] 读 _recent_actions 失败: {e}")
            return []

    def _load_archived_memories(self, agent_id: str) -> list[dict]:
        """
        从 archiver_fallback/{session_id}/{agent_id}_*.json 读所有归档文件,
        转成前端 Memory 形状。
        """
        if not self._archiver:
            return []
        session_id = getattr(self._archiver, "_session_id", None) or "default"
        session_dir = self._fallback_dir / session_id
        if not session_dir.exists():
            return []

        out: list[dict] = []
        try:
            for json_file in sorted(session_dir.glob(f"{agent_id}_*.json")):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    out.append(self._summary_dict_to_memory(data))
                except Exception as e:
                    logger.debug(f"[timeline] 读归档失败 {json_file}: {e}")
        except Exception as e:
            logger.warning(f"[timeline] 列归档目录失败 {session_dir}: {e}")

        return out

    def _synthesize_from_recent(self, agent_id: str) -> list[dict]:
        """
        没有归档时,从 _recent_dialogues 截取该 agent 参与的对话,合成 Memory 条目。
        importance/emotion 兜底值;is_core=False;context 显示对话双方。
        """
        synth: list[dict] = []
        for d in self._safe_recent_dialogues():
            # 兼容 from_id / to_id 多种命名
            from_id = d.get("from_id") or d.get("from")
            to_id = d.get("to_id") or d.get("to")
            from_name = d.get("from", from_id or "")
            to_name = d.get("to", to_id or "")
            if agent_id not in (from_id, to_id):
                continue
            tick = int(d.get("tick", 0) or 0)
            synth.append({
                "memory_id": f"synth_{tick}_{from_id}_{to_id}",
                "content": d.get("utterance", "") or "",
                "emotion": "neutral",
                "importance": 0.3,
                "tick_created": tick,
                "is_core": False,
                "context": f"{from_name} → {to_name}",
            })
        return synth

    @staticmethod
    def _summary_dict_to_memory(d: dict) -> dict:
        """MemorySummary dataclass 字典 → 前端 Memory 形状。"""
        participants = d.get("participants") or []
        if isinstance(participants, str):
            participants = [x.strip() for x in participants.split(",") if x.strip()]
        return {
            "memory_id": d.get("memory_id", ""),
            "content": d.get("summary_text") or d.get("content") or "",
            "emotion": d.get("emotion", "neutral"),
            "importance": float(d.get("importance_score", d.get("importance", 0.5)) or 0.5),
            "tick_created": int(d.get("tick_created", 0) or 0),
            "is_core": bool(d.get("core_memory", d.get("is_core", False))),
            "context": ", ".join(participants) if participants else "",
        }
