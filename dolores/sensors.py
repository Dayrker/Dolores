"""系统状态感知：跨平台读取 CPU/内存/负载，不依赖 psutil。

- Linux/WSL：读 /proc/stat、/proc/meminfo、os.getloadavg()。
- Windows：用 ctypes 调 kernel32（GetSystemTimes / GlobalMemoryStatusEx）。
- 其它平台：优雅降级（available=False）。
产出 SystemState 快照，供人设层映射成情绪。用 create_sensor() 按平台选实现。
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


class BaseSensor:
    """传感器基类：负责时间/夜间判断等平台无关逻辑。"""

    def __init__(self, night_start: int = 1, night_end: int = 6):
        self.night_start = night_start
        self.night_end = night_end
        self.n_cpu = os.cpu_count() or 1

    def _time_fields(self):
        now = time.localtime()
        hour = now.tm_hour
        if self.night_start <= self.night_end:
            is_night = self.night_start <= hour < self.night_end
        else:
            is_night = hour >= self.night_start or hour < self.night_end
        return hour, now.tm_wday, is_night

    def read(self) -> SystemState:  # pragma: no cover - 子类实现
        raise NotImplementedError


class LinuxSystemSensor(BaseSensor):
    """读取 /proc 的 Linux/WSL 传感器。CPU% 需两次采样差分。"""

    def __init__(self, night_start: int = 1, night_end: int = 6):
        super().__init__(night_start, night_end)
        self._prev_cpu: Optional[Tuple[int, int]] = None  # (idle, total)
        self._read_cpu_times()  # 预热

    @staticmethod
    def _read_cpu_times() -> Optional[Tuple[int, int]]:
        try:
            with open("/proc/stat", "r") as f:
                parts = f.readline().split()
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

    def read(self) -> SystemState:
        hour, wday, is_night = self._time_fields()
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
            weekday=wday,
            is_night=is_night,
            available=True,
        )


class WindowsSystemSensor(BaseSensor):
    """用 ctypes 调 kernel32 的 Windows 传感器（无需 psutil）。"""

    def __init__(self, night_start: int = 1, night_end: int = 6):
        super().__init__(night_start, night_end)
        import ctypes  # 延迟导入，仅 Windows 用
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._k32 = ctypes.windll.kernel32
        self._prev_cpu: Optional[Tuple[int, int]] = None  # (idle, busy)
        self._start = time.time()
        self._read_cpu_times()  # 预热

    # GetSystemTimes 返回 idle/kernel/user 三个 FILETIME（kernel 含 idle）
    def _read_cpu_times(self) -> Optional[Tuple[int, int]]:
        try:
            ft = self._wintypes.FILETIME
            idle, kernel, user = ft(), ft(), ft()
            ok = self._k32.GetSystemTimes(
                self._ctypes.byref(idle),
                self._ctypes.byref(kernel),
                self._ctypes.byref(user),
            )
            if not ok:
                return None

            def to64(f):
                return (f.dwHighDateTime << 32) | f.dwLowDateTime

            idle_t = to64(idle)
            total_t = to64(kernel) + to64(user)  # kernel 已含 idle
            busy_t = total_t - idle_t
            return idle_t, busy_t
        except Exception:
            return None

    def _cpu_percent(self) -> float:
        cur = self._read_cpu_times()
        if cur is None:
            return 0.0
        if self._prev_cpu is None:
            self._prev_cpu = cur
            return 0.0
        idle0, busy0 = self._prev_cpu
        idle1, busy1 = cur
        self._prev_cpu = cur
        didle = idle1 - idle0
        dbusy = busy1 - busy0
        dtotal = didle + dbusy
        if dtotal <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * dbusy / dtotal))

    def _mem(self) -> Tuple[float, int, int]:
        try:
            ctypes = self._ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_uint32),
                    ("dwMemoryLoad", ctypes.c_uint32),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not self._k32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return 0.0, 0, 0
            total_mb = int(stat.ullTotalPhys // (1024 * 1024))
            used_mb = int((stat.ullTotalPhys - stat.ullAvailPhys) // (1024 * 1024))
            return float(stat.dwMemoryLoad), used_mb, total_mb
        except Exception:
            return 0.0, 0, 0

    def read(self) -> SystemState:
        hour, wday, is_night = self._time_fields()
        cpu = self._cpu_percent()
        mem_pct, used_mb, total_mb = self._mem()
        # Windows 无 loadavg：用 CPU% 折算一个近似值，仅用于摘要展示
        load1 = round(cpu / 100.0 * self.n_cpu, 2)
        return SystemState(
            cpu_percent=round(cpu, 1),
            mem_percent=round(mem_pct, 1),
            mem_used_mb=used_mb,
            mem_total_mb=total_mb,
            load1=load1,
            load5=load1,
            load15=load1,
            n_cpu=self.n_cpu,
            uptime_s=time.time() - self._start,
            hour=hour,
            weekday=wday,
            is_night=is_night,
            available=True,
        )


class NullSensor(BaseSensor):
    """未知平台兜底：只给时间，其余为 0、available=False。"""

    def read(self) -> SystemState:
        hour, wday, is_night = self._time_fields()
        return SystemState(
            hour=hour, weekday=wday, is_night=is_night,
            n_cpu=self.n_cpu, available=False,
        )


def create_sensor(night_start: int = 1, night_end: int = 6) -> BaseSensor:
    """按平台选择传感器实现。"""
    if os.name == "nt":
        try:
            return WindowsSystemSensor(night_start, night_end)
        except Exception:
            return NullSensor(night_start, night_end)
    if os.path.exists("/proc/stat"):
        return LinuxSystemSensor(night_start, night_end)
    return NullSensor(night_start, night_end)


# 向后兼容：保留旧名字（指向 Linux 实现）
SystemSensor = LinuxSystemSensor
