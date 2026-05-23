"""
journal.py — V0.6 日记 API + Timeline API
提供角色记忆日记和世界大事记的查询接口
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """时间线事件"""
    tick: int
    event_type: str  # "narrative_event" | "relationship_change" | "dialogue_milestone"
    description: str
    participants: list[str]


class JournalService:
    """
    日记服务
    管理角色记忆的查询和展示
    """

    def __init__(self, retriever, archiver, forgetting_curve=None):
        """
        Args:
            retriever: MemoryRetriever 实例
            archiver: MemoryArchiver 实例
            forgetting_curve: ForgettingCurve 实例（可选）
        """
        self._retriever = retriever
        self._archiver = archiver
        self._forgetting_curve = forgetting_curve

    async def get_journal(
        self,
        agent_id: str,
        page: int = 1,
        size: int = 10,
        include_fading: bool = False,
    ) -> dict:
        """
        获取角色的记忆日记

        Args:
            agent_id: 角色 ID
            page: 页码（从1开始）
            size: 每页数量
            include_fading: 是否包含正在衰减的记忆

        Returns:
            {"entries": [...], "total": int, "page": int}
        """
        if not self._retriever:
            logger.warning("[JournalService] retriever 未初始化")
            return {"entries": [], "total": 0, "page": page}

        try:
            # 获取记忆条目
            entries = await self._retriever.list_entries(agent_id, offset=0, limit=100)

            # 计算 decay_score 并标记 fading
            for entry in entries:
                decay = self._calculate_decay(entry.get("tick", 0))
                entry["fading"] = decay <= 0.1

            # 过滤 fading 记忆
            if not include_fading:
                entries = [e for e in entries if not e.get("fading", False)]

            # 分页
            total = len(entries)
            start = (page - 1) * size
            end = start + size
            page_entries = entries[start:end]

            return {
                "entries": page_entries,
                "total": total,
                "page": page,
                "page_size": size,
            }

        except Exception as e:
            logger.error(f"[JournalService] get_journal 失败: {e}")
            return {"entries": [], "total": 0, "page": page}

    def _calculate_decay(self, tick_created: int) -> float:
        """计算记忆的衰减分数"""
        if not self._forgetting_curve:
            return 1.0

        try:
            current_tick = getattr(self._archiver, '_tick_counter', 0) if self._archiver else 0
            return self._forgetting_curve.calculate_score(tick_created, current_tick)
        except Exception:
            return 1.0


class TimelineService:
    """
    时间线服务
    管理世界大事记的记录和查询
    """

    def __init__(self, world):
        self._world = world
        self._event_ids: set = set()  # (tick, event_type, frozenset(participants)) 去重
        self._timeline: list = []

    def record_event(
        self,
        event_type: str,
        description: str,
        participants: list[str],
        tick: int = None,
    ) -> None:
        """
        记录一个时间线事件

        Args:
            event_type: 事件类型
            description: 事件描述
            participants: 涉及的玩家 ID 列表
            tick: 时间戳（如果为 None，使用 world 的当前 tick）
        """
        if tick is None:
            tick = getattr(self._world, '_tick_id', 0)

        # 去重检查
        key = (tick, event_type, frozenset(participants))
        if key in self._event_ids:
            logger.debug(f"[Timeline] 事件去重: {key}")
            return

        self._event_ids.add(key)
        self._timeline.append({
            "tick": tick,
            "event_type": event_type,
            "description": description,
            "participants": list(participants),
        })

        logger.info(f"[Timeline] 记录事件: tick={tick}, type={event_type}, desc={description[:30]}...")

    def get_timeline(
        self,
        page: int = 1,
        size: int = 20,
        event_type: str = None,
    ) -> dict:
        """
        获取时间线事件列表

        Args:
            page: 页码
            size: 每页数量
            event_type: 过滤事件类型（可选）

        Returns:
            {"events": [...], "total": int, "page": int}
        """
        events = self._timeline

        # 按事件类型过滤
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]

        # 按 tick 倒序
        events = sorted(events, key=lambda e: e["tick"], reverse=True)

        # 分页
        total = len(events)
        start = (page - 1) * size
        end = start + size
        page_events = events[start:end]

        return {
            "events": page_events,
            "total": total,
            "page": page,
            "page_size": size,
        }

    def clear(self) -> None:
        """清空时间线（用于世界重置）"""
        self._event_ids.clear()
        self._timeline.clear()