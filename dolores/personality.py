"""人设与情绪：把系统状态映射成 Dolores 的情绪，并检测值得反应的事件。

情绪（mood）驱动立绘表情与话术风格；事件（event）驱动“自发反应”。
本模块是纯逻辑、无 IO，方便单测。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .sensors import SystemState

# 所有情绪及其对应的备用表情符号（仅供调试/降级；正式立绘见 ui/sprite.py）。
# 颜文字仅用「微软雅黑」带字形的字符，避免豆腐块。
MOODS: Dict[str, str] = {
    "happy": "(・ω・)",
    "comfy": "( ´ ▽ ` )",
    "excited": "ヾ(≧▽≦)ノ",
    "curious": "(･ω･)?",
    "worried": "(；・ω・)",
    "panic": "(°〇°)!",
    "sleepy": "(￣o￣)",
    "lonely": "(´-ω-)",
}


@dataclass
class PetState:
    """Dolores 自身的内在状态。"""

    mood: str = "happy"
    energy: float = 1.0          # 0~1，夜里会下降
    last_interaction_ts: float = field(default_factory=time.time)
    last_event: str = ""

    def note_interaction(self) -> None:
        self.last_interaction_ts = time.time()

    def idle_seconds(self) -> float:
        return time.time() - self.last_interaction_ts


@dataclass
class Event:
    """一个待反应的事件。"""

    key: str            # 如 'cpu_very_high' / 'night' / 'lonely'
    priority: int       # 数字越大越优先
    mood: str           # 触发时建议切换到的情绪


class Personality:
    """根据系统状态推导情绪 + 产生事件，带去抖动/冷却，避免话痨。"""

    def __init__(self, cfg):
        th = cfg.get("behavior.thresholds", {}) or {}
        self.cpu_high = th.get("cpu_high", 80.0)
        self.cpu_very_high = th.get("cpu_very_high", 92.0)
        self.mem_high = th.get("mem_high", 80.0)
        self.mem_very_high = th.get("mem_very_high", 92.0)
        self.idle_lonely_after = cfg.get("behavior.idle_lonely_after_s", 600)

        # 事件冷却（秒）：同一类事件在冷却期内不重复触发
        self._cooldowns: Dict[str, float] = {}
        self._cooldown_default = 120.0
        self._cooldown_overrides = {
            "night": 1800.0,     # 夜间提醒每 30 分钟最多一次
            "lonely": 600.0,
        }
        # 连续高负载需要持续若干次采样才报警，避免瞬时毛刺
        self._cpu_high_streak = 0
        self._mem_high_streak = 0
        self._streak_needed = 2

    # ---- 情绪推导 ----
    def derive_mood(self, sys: SystemState, pet: PetState) -> str:
        if not sys.available:
            return "happy"
        if sys.cpu_percent >= self.cpu_very_high or sys.mem_percent >= self.mem_very_high:
            return "panic"
        if sys.cpu_percent >= self.cpu_high or sys.mem_percent >= self.mem_high:
            return "worried"
        if sys.is_night:
            return "sleepy"
        if pet.idle_seconds() >= self.idle_lonely_after:
            return "lonely"
        # 轻负载且白天 → 看 CPU 决定是悠闲还是雀跃
        if sys.cpu_percent < 15:
            return "comfy"
        return "happy"

    # ---- 事件检测 ----
    def _ready(self, key: str, now: float) -> bool:
        cd = self._cooldown_overrides.get(key, self._cooldown_default)
        return now - self._cooldowns.get(key, -1e9) >= cd

    def _fire(self, key: str, now: float) -> None:
        self._cooldowns[key] = now

    def detect_events(self, sys: SystemState, pet: PetState) -> List[Event]:
        """返回本次采样应触发的事件（已过冷却与去抖），按优先级降序。"""
        now = time.time()
        events: List[Event] = []
        if not sys.available:
            return events

        # CPU 去抖
        if sys.cpu_percent >= self.cpu_high:
            self._cpu_high_streak += 1
        else:
            self._cpu_high_streak = 0
        if sys.mem_percent >= self.mem_high:
            self._mem_high_streak += 1
        else:
            self._mem_high_streak = 0

        # 高优先级：极高占用（同时压制同类的次级告警，避免连环弹）
        if sys.cpu_percent >= self.cpu_very_high and self._ready("cpu_very_high", now):
            events.append(Event("cpu_very_high", 100, "panic"))
            self._fire("cpu_very_high", now)
            self._fire("cpu_high", now)
        elif (
            self._cpu_high_streak >= self._streak_needed
            and self._ready("cpu_high", now)
        ):
            events.append(Event("cpu_high", 60, "worried"))
            self._fire("cpu_high", now)

        if sys.mem_percent >= self.mem_very_high and self._ready("mem_very_high", now):
            events.append(Event("mem_very_high", 95, "panic"))
            self._fire("mem_very_high", now)
            self._fire("mem_high", now)
        elif (
            self._mem_high_streak >= self._streak_needed
            and self._ready("mem_high", now)
        ):
            events.append(Event("mem_high", 55, "worried"))
            self._fire("mem_high", now)

        # 夜间关怀
        if sys.is_night and self._ready("night", now):
            events.append(Event("night", 40, "sleepy"))
            self._fire("night", now)

        # 寂寞（久未互动）
        if pet.idle_seconds() >= self.idle_lonely_after and self._ready("lonely", now):
            events.append(Event("lonely", 30, "lonely"))
            self._fire("lonely", now)

        events.sort(key=lambda e: e.priority, reverse=True)
        return events

    def top_event(self, sys: SystemState, pet: PetState) -> Optional[Event]:
        evs = self.detect_events(sys, pet)
        return evs[0] if evs else None
