"""系统状态感知：仅用 /proc 与标准库，不依赖 psutil。

产出一个 SystemState 快照（CPU% / 内存% / 负载 / 时间段等），供人设层映射成情绪。
在非 Linux 平台上会优雅降级（返回 available=False 的占位数据）。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass
class SystemState:
    """某一时刻的电脑状态快照。"""

    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    mem_used_mb: int = 0
    mem_total_mb: int = 0
    load1: float = 0.0
    load5: float = 0.0
    load15: float = 0.0
    n_cpu: int = 1
    uptime_s: float = 0.0
    hour: int = 0
    weekday: int = 0  # 0=周一
    is_night: bool = False
    available: bool = True
    extra: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        """给大脑看的一行中文摘要。"""
        return (
            f"CPU占用{self.cpu_percent:.0f}%、内存占用{self.mem_percent:.0f}%"
            f"（{self.mem_used_mb}/{self.mem_total_mb}MB）、"
            f"负载{self.load1:.2f}、现在{self.hour}点"
        )


class SystemSensor:
    """周期性采样系统状态。CPU% 需要两次采样差分，因此对象保存上一次的累计值。"""

    def __init__(self, night_start: int = 1, night_end: int = 6):
        self._prev_cpu: Optional[Tuple[int, int]] = None  # (idle, total)
        self.night_start = night_start
        self.night_end = night_end
        self.n_cpu = os.cpu_count() or 1
        # 预热一次，让首帧 CPU% 有意义
        self._read_cpu_times()

    # ---- /proc 读取 ----
    @staticmethod
    def _read_cpu_times() -> Optional[Tuple[int, int]]:
        """返回 (idle_all, total)，失败返回 None。"""
        try:
            with open("/proc/stat", "r") as f:
                parts = f.readline().split()
            # user nice system idle iowait irq softirq steal guest guest_nice
            nums = list(map(int, parts[1:]))
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)  # idle + iowait
            total = sum(nums)
            return idle, total
        except Exception:
            return None

    def _cpu_percent(self) -> float:
        cur = self._read_cpu_times()
        if cur is None:
            return 0.0
        if self._prev_cpu is None:
            self._prev_cpu = cur
            return 0.0
        idle0, total0 = self._prev_cpu
        idle1, total1 = cur
        self._prev_cpu = cur
        dtotal = total1 - total0
        didle = idle1 - idle0
        if dtotal <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (1.0 - didle / dtotal)))

    @staticmethod
    def _mem() -> Tuple[float, int, int]:
        """返回 (mem_percent, used_mb, total_mb)。"""
        try:
            info: Dict[str, int] = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    key, _, rest = line.partition(":")
                    info[key] = int(rest.strip().split()[0])  # kB
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            used = max(0, total - avail)
            pct = (100.0 * used / total) if total else 0.0
            return pct, used // 1024, total // 1024
        except Exception:
            return 0.0, 0, 0

    @staticmethod
    def _uptime() -> float:
        try:
            with open("/proc/uptime", "r") as f:
                return float(f.read().split()[0])
        except Exception:
            return 0.0

    # ---- 对外 ----
    def read(self) -> SystemState:
        now = time.localtime()
        hour = now.tm_hour
        is_night = (
            self.night_start <= hour < self.night_end
            if self.night_start <= self.night_end
            else (hour >= self.night_start or hour < self.night_end)
        )

        # 非 Linux 平台 /proc 不存在 → 降级
        if not os.path.exists("/proc/stat"):
            return SystemState(
                hour=hour, weekday=now.tm_wday, is_night=is_night, available=False
            )

        cpu = self._cpu_percent()
        mem_pct, used_mb, total_mb = self._mem()
        try:
            load1, load5, load15 = os.getloadavg()
        except (OSError, AttributeError):
            load1 = load5 = load15 = 0.0

        return SystemState(
            cpu_percent=round(cpu, 1),
            mem_percent=round(mem_pct, 1),
            mem_used_mb=used_mb,
            mem_total_mb=total_mb,
            load1=round(load1, 2),
            load5=round(load5, 2),
            load15=round(load15, 2),
            n_cpu=self.n_cpu,
            uptime_s=self._uptime(),
            hour=hour,
            weekday=now.tm_wday,
            is_night=is_night,
            available=True,
        )
