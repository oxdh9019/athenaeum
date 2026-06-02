"""
heartbeat_mode.py — V0.7 心跳模式
当周围无他人且无紧急需求时，角色进入低功耗心跳模式
大幅减少 LLM 调用频率
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatConfig:
    """心跳模式配置"""
    enabled: bool = True
    # V0.7 Phase D A1: 心跳间隔放宽, 30s tick 配合下 = 4-8 分钟/决策 (base 6 min)
    # 旧值 4-8 tick (2-4 min) 太频繁, LLM 还没"消化"上次决策就被叫醒,
    # 导致 reasoning 同质化 + 角色行为缺乏深度
    min_interval: int = 8
    max_interval: int = 16
    base_interval: int = 12  # ≈ 6 min/决策 (30s tick)


class HeartbeatMode:
    """
    心跳模式控制器
    管理角色的低功耗心跳状态
    """

    # 中断条件优先级
    PRIORITY_USER_POSSESS = 100  # 用户附身
    PRIORITY_SAFETY = 90         # 安全威胁
    PRIORITY_SOCIAL = 70         # 他人进入
    PRIORITY_NARRATIVE = 60      # 叙事事件
    PRIORITY_GOAL_DEADLINE = 40  # 目标截止临近

    def __init__(self, agent_id: str, personality: dict = None, config: HeartbeatConfig = None):
        self._agent_id = agent_id
        self._personality = personality or {}
        self._config = config or HeartbeatConfig()
        self._tick_counter = 0
        self._last_action_tick = 0
        self._is_heartbeat_mode = True
        self._heartbeat_interval = self._calculate_interval()

    def _calculate_interval(self) -> int:
        """
        根据性格计算心跳间隔

        - 高神经质：短间隔（5~8）
        - 低外向：长间隔（12~20）
        - 默认：8~12
        """
        neuroticism = self._personality.get("neuroticism", 0.5)
        extraversion = self._personality.get("extraversion", 0.5)

        # 基础间隔
        base = self._config.base_interval

        # 高神经质 → 缩短间隔（焦虑敏感）
        if neuroticism > 0.6:
            reduction = (neuroticism - 0.6) * 15  # 最多-6
            base -= reduction

        # 低外向 → 延长间隔（不喜欢频繁动作）
        if extraversion < 0.3:
            extension = (0.3 - extraversion) * 20  # 最多+6
            base += extension

        # 限制在 min/max 范围内
        return max(self._config.min_interval, min(self._config.max_interval, int(base)))

    def should_skip_tick(self, tick_counter: int) -> bool:
        """
        判断是否跳过本 Tick（不调用 LLM）

        Returns:
            True = 跳过，False = 正常执行
        """
        if not self._config.enabled:
            return False

        self._tick_counter = tick_counter

        # 计算距离上次动作的Tick数
        ticks_since_action = tick_counter - self._last_action_tick

        # 心跳间隔内应该跳过
        if ticks_since_action < self._heartbeat_interval:
            return True

        return False

    def should_interrupt(self, interrupt_reason: str, priority: int) -> bool:
        """
        判断是否中断心跳模式

        Args:
            interrupt_reason: 中断原因描述
            priority: 优先级（0-100）

        Returns:
            True = 中断心跳模式，立即执行动作
        """
        if priority >= self.PRIORITY_SAFETY:
            logger.info(f"[HeartbeatMode] [{self._agent_id}] 安全中断: {interrupt_reason}")
            return True

        if priority >= self.PRIORITY_SOCIAL:
            logger.info(f"[HeartbeatMode] [{self._agent_id}] 社交中断: {interrupt_reason}")
            return True

        return False

    def get_idle_action(self) -> dict:
        """
        获取心跳模式下应执行的空闲动作

        Returns:
            空闲动作描述字典
        """
        # 随机选择空闲动作
        idle_actions = [
            {"action_type": "idle", "description": "发呆片刻"},
            {"action_type": "observe", "description": "观察周围环境"},
            {"action_type": "idle", "description": "整理随身物品"},
            {"action_type": "observe", "description": "倾听周围的声音"},
        ]

        import random
        action = random.choice(idle_actions)
        action["is_heartbeat"] = True
        action["heartbeat_interval"] = self._heartbeat_interval

        return action

    def on_action_executed(self, tick_counter: int):
        """动作执行后，重置心跳计时器"""
        self._last_action_tick = tick_counter
        self._is_heartbeat_mode = True
        logger.debug(
            f"[HeartbeatMode] [{self._agent_id}] 动作执行，下一跳心跳 "
            f"在 {self._heartbeat_interval} Tick 后"
        )

    def on_social_entered(self):
        """检测到他人进入同一地点"""
        self._is_heartbeat_mode = False

    def on_social_left(self):
        """他人离开，恢复心跳模式"""
        self._is_heartbeat_mode = True

    def get_interval(self) -> int:
        """获取当前心跳间隔"""
        return self._heartbeat_interval

    def is_active(self) -> bool:
        """是否处于心跳模式"""
        return self._is_heartbeat_mode

    def update_personality(self, personality: dict):
        """更新性格参数，重算心跳间隔"""
        self._personality = personality
        self._heartbeat_interval = self._calculate_interval()
        logger.info(
            f"[HeartbeatMode] [{self._agent_id}] 性格更新，"
            f"心跳间隔调整为 {self._heartbeat_interval} Tick"
        )

    def sync_tick(self, tick_counter: int):
        """同步 Tick 计数器"""
        self._tick_counter = tick_counter

    def check_goal_deadline_pressure(self, active_goal, current_tick: int) -> bool:
        """
        检查目标截止日期压力

        Args:
            active_goal: 当前活跃目标
            current_tick: 当前 Tick

        Returns:
            True = 压力过大，应中断心跳
        """
        if not active_goal:
            return False

        deadline = active_goal.deadline_tick
        if deadline is None:
            return False

        # 目标截止时间在 10 Tick 内
        ticks_until_deadline = deadline - current_tick
        if 0 < ticks_until_deadline <= 10:
            logger.info(
                f"[HeartbeatMode] [{self._agent_id}] 目标截止压力: "
                f"{active_goal.description} 还有 {ticks_until_deadline} Tick"
            )
            return True

        return False

    def get_status(self) -> dict:
        """获取心跳模式状态（用于调试）"""
        return {
            "agent_id": self._agent_id,
            "is_active": self._is_heartbeat_mode,
            "heartbeat_interval": self._heartbeat_interval,
            "ticks_since_action": self._tick_counter - self._last_action_tick,
            "last_action_tick": self._last_action_tick,
            "current_tick": self._tick_counter,
        }