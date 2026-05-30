"""图片立绘加载器：从 assets/sprites/<pack>/ 加载帧序列与 manifest。

支持用户自定义立绘包：把同样目录结构（manifest.json + <action>_<NN>.png）放进
assets/sprites/<yourpack>/，在 config 里把 ui.sprite.pack 指过去即可。
加载失败（目录/manifest 缺失或损坏）返回 None，上层据此回退到矢量立绘。

manifest.json 结构：
{
  "name": "default", "size": 140, "fps": 12, "anchor": "bottom-center",
  "actions": { "idle": {"frames":4,"loop":true,"fps":6}, ... },
  "mood_map": { "happy":"idle", "excited":"bounce", ... }
}
帧文件命名：<action>_<index:02d>.png（如 idle_00.png）。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, Optional

from PIL import Image

logger = logging.getLogger("dolores.ui.sprite_loader")

DEFAULT_MOOD_MAP = {
    "happy": "idle", "comfy": "idle", "curious": "idle", "worried": "idle",
    "lonely": "idle", "excited": "bounce", "panic": "panic", "sleepy": "sleep",
}


class SpritePack:
    """一个立绘包：按需加载、缓存帧图。"""

    def __init__(self, directory: str, manifest: dict):
        self.dir = directory
        self.name = manifest.get("name", os.path.basename(directory))
        self.src_size = int(manifest.get("size", 140))
        self.default_fps = int(manifest.get("fps", 12))
        self.anchor = manifest.get("anchor", "bottom-center")
        self.actions: Dict[str, dict] = manifest.get("actions", {})
        self.mood_map: Dict[str, str] = manifest.get("mood_map", DEFAULT_MOOD_MAP)
        self._cache: Dict[tuple, Image.Image] = {}

    # ---- 查询 ----
    def has_action(self, action: str) -> bool:
        return action in self.actions

    def frame_count(self, action: str) -> int:
        return int(self.actions.get(action, {}).get("frames", 1))

    def loop(self, action: str) -> bool:
        return bool(self.actions.get(action, {}).get("loop", False))

    def fps(self, action: str) -> int:
        return int(self.actions.get(action, {}).get("fps", self.default_fps))

    def action_for_mood(self, mood: str) -> str:
        action = self.mood_map.get(mood, "idle")
        return action if self.has_action(action) else ("idle" if self.has_action("idle") else action)

    # ---- 取帧 ----
    def frame(self, action: str, index: int, size: int) -> Optional[Image.Image]:
        n = self.frame_count(action)
        if n <= 0:
            return None
        index = index % n
        key = (action, index, size)
        if key in self._cache:
            return self._cache[key]
        path = os.path.join(self.dir, f"{action}_{index:02d}.png")
        if not os.path.exists(path):
            return None
        try:
            img = Image.open(path).convert("RGBA")
            if img.size != (size, size + 8):
                img = self._fit(img, size)
            self._cache[key] = img
            return img
        except Exception as exc:  # noqa: BLE001
            logger.warning("帧加载失败 %s：%s", path, exc)
            return None

    def _fit(self, img: Image.Image, size: int) -> Image.Image:
        """把任意尺寸帧缩放并按 anchor 贴到 size×(size+8) 画布（与矢量帧一致）。"""
        # 等比缩放到不超过 size
        w, h = img.size
        scale = min(size / w, size / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size + 8), (0, 0, 0, 0))
        x = (size - nw) // 2
        if "bottom" in self.anchor:
            y = (size + 8) - nh
        elif "top" in self.anchor:
            y = 0
        else:
            y = (size + 8 - nh) // 2
        canvas.alpha_composite(img, (x, max(0, y)))
        return canvas


def load_pack(assets_dir: str, pack_name: str) -> Optional[SpritePack]:
    """加载立绘包；失败返回 None（触发矢量回退）。"""
    directory = os.path.join(assets_dir, pack_name)
    manifest_path = os.path.join(directory, "manifest.json")
    if not os.path.isfile(manifest_path):
        logger.info("未找到立绘包 manifest：%s（将用矢量立绘）", manifest_path)
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as exc:  # noqa: BLE001
        logger.warning("立绘包 manifest 解析失败：%s", exc)
        return None

    pack = SpritePack(directory, manifest)
    # 校验：至少 idle 的首帧要存在
    if not pack.actions:
        logger.warning("立绘包无 actions：%s", directory)
        return None
    probe = "idle" if pack.has_action("idle") else next(iter(pack.actions))
    if pack.frame(probe, 0, pack.src_size) is None:
        logger.warning("立绘包帧文件缺失：%s/%s_00.png", directory, probe)
        return None
    logger.info("已加载立绘包：%s（%d 个动作）", pack.name, len(pack.actions))
    return pack
