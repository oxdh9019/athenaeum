"""
llm_budget.py — V0.7 LLM 调用预算门
控制单 tick 内 LLM 并发数与硬上限,避免本地模型过载。
"""

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMBudget:
    """
    每 tick 重置的 LLM 调用预算门。
    - semaphore 限制同时 in-flight 的 LLM 数
    - per_tick_counter 记录本 tick 已发起调用,超限排队
    - 调用方:在 chat() 入口 await acquire,完成后 release + record_call
    """

    max_concurrent: int = 2
    max_per_tick: int = 4
    _semaphore: asyncio.Semaphore = field(init=False)
    _per_tick_counter: int = 0
    _current_tick: int = 0

    def __post_init__(self):
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    def on_tick_start(self, tick_id: int) -> None:
        """每个 tick 开始时调用,重置 per-tick 计数"""
        self._per_tick_counter = 0
        self._current_tick = tick_id
        logger.debug(f"[LLMBudget] tick={tick_id} 预算重置 (max_per_tick={self.max_per_tick})")

    def can_call(self) -> bool:
        return self._per_tick_counter < self.max_per_tick

    async def acquire(self) -> bool:
        """
        获取调用许可。返回 False 表示本 tick 配额已满,调用方应跳过。
        """
        if not self.can_call():
            logger.debug(f"[LLMBudget] tick={self._current_tick} per-tick 配额已满,跳过")
            return False
        await self._semaphore.acquire()
        return True

    def release(self) -> None:
        try:
            self._semaphore.release()
        except ValueError:
            pass

    def record_call(self) -> None:
        self._per_tick_counter += 1

    def get_stats(self) -> dict:
        return {
            "current_tick": self._current_tick,
            "per_tick_count": self._per_tick_counter,
            "max_per_tick": self.max_per_tick,
            "max_concurrent": self.max_concurrent,
        }
