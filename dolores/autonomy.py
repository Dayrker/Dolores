"""自主行为引擎：决定 Dolores 何时“自己开口”。

这是“仿佛有自主意识”的核心——它不直接生成文字（那是大脑的事），
而是基于时间与状态，决定每次心跳要不要产生一个 Intent（说话意图）。

两类驱动：
1) 事件驱动：高优先级状态变化（CPU 爆表、夜深）→ 立即反应；
2) 时间驱动：随机间隔的自发闲聊，让它显得鲜活、有存在感。

设计为纯决策、无 IO、无线程，便于上层（app）按心跳调用与单测。
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from .personality import Event, Personality, PetState
from .sensors import SystemState


@dataclass
class Intent:
    """一次“想说话”的意图，交给大脑去生成具体文字。"""

    kind: str            # 'event' | 'autonomy' | 'greeting'
    mood: str
    event: str = ""


class AutonomyEngine:
    """根据心跳决定是否产生说话意图。"""

    def __init__(self, cfg, personality: Personality, rng: Optional[random.Random] = None):
        self.personality = personality
        self.min_interval = cfg.get("behavior.autonomy_min_interval_s", 35)
        self.max_interval = cfg.get("behavior.autonomy_max_interval_s", 90)
        qh = cfg.get("behavior.quiet_hours", {}) or {}
        self.quiet_start = qh.get("start", 1)
        self.quiet_end = qh.get("end", 6)

        self._rng = rng or random.Random()
        self._next_chat_ts = time.time() + self._roll_interval()
        self._greeted = False

    def _roll_interval(self) -> float:
        lo, hi = self.min_interval, max(self.min_interval, self.max_interval)
        return self._rng.uniform(lo, hi)

    def _in_quiet_hours(self, sys: SystemState) -> bool:
        """安静时段：减少自发闲聊（但不屏蔽紧急事件）。"""
        h = sys.hour
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= h < self.quiet_end
        return h >= self.quiet_start or h < self.quiet_end

    def reset_chat_timer(self, scale: float = 1.0) -> None:
        """说完话后重置下一次自发闲聊计时（scale>1 可拉长间隔）。"""
        self._next_chat_ts = time.time() + self._roll_interval() * scale

    def need_greeting(self) -> bool:
        return not self._greeted

    def mark_greeted(self) -> None:
        self._greeted = True

    def tick(self, sys: SystemState, pet: PetState) -> Optional[Intent]:
        """每个心跳调用一次；返回 Intent 或 None。

        优先级：开场问候 > 紧急事件 > 定时自发闲聊。
        """
        now = time.time()

        # 1) 启动问候
        if not self._greeted:
            self._greeted = True
            mood = self.personality.derive_mood(sys, pet)
            self.reset_chat_timer()
            return Intent(kind="greeting", mood=mood)

        # 2) 事件驱动（紧急事件即便在安静时段也会触发）
        ev: Optional[Event] = self.personality.top_event(sys, pet)
        if ev is not None:
            # 安静时段里，仅放行高优先级（panic/worried 类）事件
            if self._in_quiet_hours(sys) and ev.priority < 50 and ev.key != "night":
                pass
            else:
                self.reset_chat_timer()
                return Intent(kind="event", mood=ev.mood, event=ev.key)

        # 3) 定时自发闲聊
        if now >= self._next_chat_ts:
            self.reset_chat_timer(scale=2.0 if self._in_quiet_hours(sys) else 1.0)
            if self._in_quiet_hours(sys):
                # 安静时段大幅降低闲聊概率
                if self._rng.random() > 0.25:
                    return None
            mood = self.personality.derive_mood(sys, pet)
            return Intent(kind="autonomy", mood=mood)

        return None
