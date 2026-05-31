---
name: cross-platform-system-metrics
description: Read CPU%, memory, and load on Linux and Windows using only the standard library (no psutil). Use when you need lightweight system monitoring, can't/won't add the psutil dependency, are in an offline environment, or must support both /proc (Linux/WSL) and native Windows from one codebase.
keywords: [system metrics, CPU percent, memory, psutil alternative, /proc, GetSystemTimes, GlobalMemoryStatusEx, ctypes, MEMORYSTATUSEX, FILETIME, loadavg, WSL, Windows]
---

# Cross-platform system metrics without psutil

When psutil isn't available (offline, frozen env, policy), read metrics from the OS
directly. Design: a `BaseSensor` with shared time logic, one impl per platform, and a
`create_sensor()` factory that picks by `os.name` / `/proc` presence. CPU% always needs
**two samples differenced** — prime once in `__init__`, store the previous cumulative value.

## Linux / WSL — read /proc

```python
def _cpu_times():                       # returns (idle_all, total)
    with open("/proc/stat") as f:
        n = list(map(int, f.readline().split()[1:]))
    return n[3] + n[4], sum(n)          # idle+iowait, total

# cpu% = 1 - d_idle / d_total  between two samples

def _mem():                             # returns (percent, used_mb, total_mb)
    info = {}
    for line in open("/proc/meminfo"):
        k, _, rest = line.partition(":"); info[k] = int(rest.split()[0])   # kB
    total, avail = info["MemTotal"], info.get("MemAvailable", info.get("MemFree", 0))
    used = total - avail
    return 100.0*used/total, used//1024, total//1024

# load: os.getloadavg()    uptime: float(open("/proc/uptime").read().split()[0])
```

## Windows — ctypes against kernel32 (no psutil)

CPU% from `GetSystemTimes` (FILETIMEs; **kernel time already includes idle**, so
`total = kernel + user`, `busy = total - idle`). Memory from `GlobalMemoryStatusEx`
(`dwMemoryLoad` is the % directly).

```python
import ctypes
from ctypes import wintypes
k32 = ctypes.windll.kernel32

def cpu_times():                        # returns (idle, busy)
    ft = wintypes.FILETIME
    idle, kernel, user = ft(), ft(), ft()
    if not k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    to64 = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
    idle_t = to64(idle); total_t = to64(kernel) + to64(user)   # kernel includes idle
    return idle_t, total_t - idle_t
# cpu% = d_busy / (d_idle + d_busy)

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
                ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64)]
def mem():
    s = MEMORYSTATUSEX(); s.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    k32.GlobalMemoryStatusEx(ctypes.byref(s))
    total_mb = s.ullTotalPhys // (1024*1024)
    used_mb  = (s.ullTotalPhys - s.ullAvailPhys) // (1024*1024)
    return float(s.dwMemoryLoad), used_mb, total_mb
# Windows has no loadavg -> report 0.0 or synthesize cpu%*n_cpu (only for display).
```

## Factory + gotchas

```python
def create_sensor(night_start=1, night_end=6):
    if os.name == "nt":     return WindowsSystemSensor(...)   # wrap ctypes in try/except -> NullSensor
    if os.path.exists("/proc/stat"): return LinuxSystemSensor(...)
    return NullSensor(...)   # unknown platform: available=False, time only, never crash
```

- **WSL is `posix` with `/proc`** → it uses the Linux sensor and reports the **Linux VM's**
  CPU/mem, not the Windows host's. Run natively on Windows for host metrics.
- First CPU% reading is always 0 (no prior sample) — that's expected; correct after 1 tick.
- Define `MEMORYSTATUSEX` with `dwLength` set before the call or it fails silently.

> Reference: `dolores/sensors.py` (`BaseSensor`, `LinuxSystemSensor`,
> `WindowsSystemSensor`, `NullSensor`, `create_sensor`).
