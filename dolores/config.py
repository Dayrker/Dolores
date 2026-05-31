"""配置加载：读取项目根目录的 config.json，提供带默认值的访问。

设计原则：即使 config.json 缺失或字段不全，也能用内置默认值正常启动。
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger("dolores.config")

# 项目根目录（本文件位于 <root>/dolores/config.py）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

# 内置默认配置——与 config.json 保持同构，作为兜底。
DEFAULTS: Dict[str, Any] = {
    "character": {
        "name": "Dolores",
        "name_cn": "朵拉",
        "species": "电子精灵",
        "self_intro": "一只住在你电脑里、会观察你电脑状态的萌系小精灵",
    },
    "model": {
        "enabled": True,
        "backend": "auto",
        "path": "models/Qwen3.5-0.8B",
        "device": "auto",
        "max_new_tokens": 80,
        "temperature": 0.85,
        "top_p": 0.9,
        "load_in_background": True,
        "ollama": {
            "host": "http://127.0.0.1:11434",
            "model": "qwen3:0.6b",
            "keep_alive": "5m",
            "request_timeout": 60,
            "think": False,
        },
    },
    "ui": {
        "pet_size": 140,
        "start_corner": "bottom-right",
        "margin": 24,
        "topmost": True,
        "bubble_max_chars": 40,
        "bubble_duration_ms": 6500,
        "theme": "pink",
        "font_family": "",
        "click_through_idle": False,
        "sprite": {
            "mode": "auto",
            "asset_dir": "assets/sprites",
            "pack": "default",
        },
    },
    "behavior": {
        "sensor_interval_ms": 2000,
        "autonomy_min_interval_s": 35,
        "autonomy_max_interval_s": 90,
        "idle_lonely_after_s": 600,
        "thresholds": {
            "cpu_high": 80.0,
            "cpu_very_high": 92.0,
            "mem_high": 80.0,
            "mem_very_high": 92.0,
        },
        "quiet_hours": {"start": 1, "end": 6},
    },
    "logging": {
        "level": "INFO",
        "to_file": False,
        "file": "dolores.log",
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并 override 到 base 的副本上（override 优先）。"""
    out = copy.deepcopy(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


class Config:
    """点路径访问的配置对象，例：cfg.get('ui.pet_size', 140)。"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def section(self, name: str) -> Dict[str, Any]:
        val = self._data.get(name, {})
        return val if isinstance(val, dict) else {}

    @property
    def root_dir(self) -> str:
        return ROOT_DIR

    def abspath(self, rel: str) -> str:
        """把相对路径解析成基于项目根目录的绝对路径。"""
        if os.path.isabs(rel):
            return rel
        return os.path.normpath(os.path.join(ROOT_DIR, rel))

    def as_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)


def load_config(path: str | None = None) -> Config:
    """加载配置；缺失或损坏时回退到默认值（不抛异常）。"""
    path = path or CONFIG_PATH
    data = DEFAULTS
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            data = _deep_merge(DEFAULTS, user)
            logger.debug("已加载配置: %s", path)
        except Exception as exc:  # noqa: BLE001 —— 配置坏掉也要能跑
            logger.warning("配置解析失败(%s)，使用默认配置: %s", path, exc)
            data = copy.deepcopy(DEFAULTS)
    else:
        logger.info("未找到 %s，使用内置默认配置", path)
        data = copy.deepcopy(DEFAULTS)
    return Config(data)
