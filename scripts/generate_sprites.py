"""生成默认图片立绘包：把萌系小精灵渲染成多动作多帧 PNG + manifest.json。

运行：
  python scripts/generate_sprites.py [--size 140] [--out assets/sprites/default]

这是构建期脚本（开发者/安装器运行），运行时 App 不写 assets。
艺术风格与 dolores/ui/sprite.py 的矢量小精灵一致，并加入动作运动：
  idle(浮动) / blink(眨眼) / bounce(蹦跶squash&stretch) /
  wave(挥手) / sleep(睡觉+zzZ) / panic(惊慌抖动)
用户可仿照本脚本输出或直接替换 PNG 来自定义立绘。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw

# 允许从项目根导入 dolores
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dolores.ui.sprite import THEMES, _eyes, _mouth  # 复用表情绘制

SS = 3  # 超采样倍率


def _canvas(size: int):
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), S


def _arm(d, cx, cy, s, side, angle_deg, c):
    """画一只小手臂（小圆 nub），side=-1 左 / +1 右，angle 控制摆动。"""
    base_x = cx + side * int(50 * s)
    base_y = cy + int(20 * s)
    ang = math.radians(angle_deg)
    ex = base_x + side * int(18 * s) * math.cos(ang)
    ey = base_y - int(18 * s) * math.sin(ang)
    d.line([base_x, base_y, ex, ey], fill=c["body_edge"], width=max(2, int(6 * s)))
    r = int(8 * s)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=c["body"], outline=c["body_edge"],
              width=max(1, int(2 * s)))


def _body(d, S, s, c, squash=1.0, dy=0):
    """画身体，squash<1 压扁、>1 拉长（蹦跶用）。返回脸中心 (cx, cy)。"""
    cx = S // 2
    cy = int(S * 0.52) + dy
    bw = int(S * 0.66 / squash)
    bh = int(S * 0.64 * squash)
    box = [cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2]
    # 阴影
    d.ellipse([box[0] + int(6*s), box[1] + int(10*s), box[2] + int(6*s), box[3] + int(10*s)],
              fill=c["shade"])
    d.ellipse(box, fill=c["body"], outline=c["body_edge"], width=max(2, int(3 * s)))
    # 呆毛
    th = int(S * 0.12)
    d.line([cx, box[1] - th, cx - int(6*s), box[1] + int(4*s)], fill=c["body_edge"], width=max(2, int(3*s)))
    d.line([cx, box[1] - th, cx + int(8*s), box[1] + int(2*s)], fill=c["body_edge"], width=max(2, int(3*s)))
    # 高光
    d.ellipse([cx - int(bw*0.28), cy - int(bh*0.30),
               cx - int(bw*0.28) + int(22*s), cy - int(bh*0.30) + int(26*s)], fill=c["highlight"])
    # 腮红
    br = int(10 * s)
    for sx in (-1, 1):
        bx = cx + sx * int(30 * s)
        d.ellipse([bx - br, cy + int(6*s) - int(br*0.7), bx + br, cy + int(6*s) + int(br*0.7)],
                  fill=c["blush"])
    return cx, cy


def _zzz(d, cx, cy, s, c, t):
    """睡觉的 zzZ（矢量描边，避免字体依赖）。t 控制飘动。"""
    col = c["eye"]
    x0 = cx + int(45 * s)
    y0 = cy - int(40 * s) - int(t * 6 * s)
    for i, sz in enumerate((10, 8, 6)):
        z = int(sz * s)
        x = x0 + i * int(10 * s)
        y = y0 - i * int(12 * s)
        d.line([x, y, x + z, y], fill=col, width=max(1, int(1.5 * s)))
        d.line([x + z, y, x, y + z], fill=col, width=max(1, int(1.5 * s)))
        d.line([x, y + z, x + z, y + z], fill=col, width=max(1, int(1.5 * s)))


def _compose(img: Image.Image, size: int) -> Image.Image:
    """超采样图缩到 size，再放到 size×(size+8) 画布（底对齐，与矢量帧一致）。"""
    base = img.resize((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size + 8), (0, 0, 0, 0))
    canvas.alpha_composite(base, (0, 8))
    return canvas


# ---- 各动作的帧生成 ----

def frames_idle(size, theme, n=4):
    c = THEMES[theme]; out = []
    for i in range(n):
        img, d, S = _canvas(size); s = SS * (size / 140.0)
        dy = int(round(3 * SS * math.sin(i / n * 2 * math.pi)))
        cx, cy = _body(d, S, s, c, dy=dy)
        _eyes(d, cx, cy, s, "happy", c); _mouth(d, cx, cy, s, "happy", c)
        out.append(_compose(img, size))
    return out


def frames_blink(size, theme, n=2):
    c = THEMES[theme]; out = []
    for i in range(n):
        img, d, S = _canvas(size); s = SS * (size / 140.0)
        cx, cy = _body(d, S, s, c)
        mood = "happy" if i == 0 else "sleepy"  # 第二帧闭眼（用 sleepy 的弯眼）
        _eyes(d, cx, cy, s, mood, c); _mouth(d, cx, cy, s, "happy", c)
        out.append(_compose(img, size))
    return out


def frames_bounce(size, theme, n=6):
    c = THEMES[theme]; out = []
    for i in range(n):
        img, d, S = _canvas(size); s = SS * (size / 140.0)
        ph = i / n
        squash = 1.0 + 0.12 * math.sin(ph * 2 * math.pi)
        dy = -int(round(10 * SS * abs(math.sin(ph * math.pi))))
        cx, cy = _body(d, S, s, c, squash=squash, dy=dy)
        _eyes(d, cx, cy, s, "excited", c); _mouth(d, cx, cy, s, "excited", c)
        out.append(_compose(img, size))
    return out


def frames_wave(size, theme, n=6):
    c = THEMES[theme]; out = []
    for i in range(n):
        img, d, S = _canvas(size); s = SS * (size / 140.0)
        cx, cy = _body(d, S, s, c)
        _eyes(d, cx, cy, s, "happy", c); _mouth(d, cx, cy, s, "happy", c)
        angle = 50 + 35 * math.sin(i / n * 2 * math.pi)  # 右手上下挥
        _arm(d, cx, cy, s, +1, angle, c)
        _arm(d, cx, cy, s, -1, -10, c)
        out.append(_compose(img, size))
    return out


def frames_sleep(size, theme, n=4):
    c = THEMES[theme]; out = []
    for i in range(n):
        img, d, S = _canvas(size); s = SS * (size / 140.0)
        dy = int(round(2 * SS * math.sin(i / n * 2 * math.pi)))
        cx, cy = _body(d, S, s, c, dy=dy)
        _eyes(d, cx, cy, s, "sleepy", c); _mouth(d, cx, cy, s, "sleepy", c)
        _zzz(d, cx, cy, s, c, i / n)
        out.append(_compose(img, size))
    return out


def frames_panic(size, theme, n=4):
    c = THEMES[theme]; out = []
    for i in range(n):
        img, d, S = _canvas(size); s = SS * (size / 140.0)
        shake = int(round(4 * SS * (1 if i % 2 == 0 else -1)))
        # 通过整体平移制造抖动
        cx, cy = _body(d, S, s, c)
        _eyes(d, cx, cy, s, "panic", c); _mouth(d, cx, cy, s, "panic", c)
        frame = _compose(img, size)
        if shake:
            shifted = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            shifted.alpha_composite(frame, (max(0, shake), 0))
            frame = shifted
        out.append(frame)
    return out


ACTIONS = {
    "idle":   (frames_idle, 4, True, 6),
    "blink":  (frames_blink, 2, False, 6),
    "bounce": (frames_bounce, 6, False, 14),
    "wave":   (frames_wave, 6, False, 12),
    "sleep":  (frames_sleep, 4, True, 4),
    "panic":  (frames_panic, 4, True, 16),
}

MOOD_MAP = {
    "happy": "idle", "comfy": "idle", "curious": "idle", "worried": "idle",
    "lonely": "idle", "excited": "bounce", "panic": "panic", "sleepy": "sleep",
}


def generate(size: int, out_dir: str, theme: str = "pink") -> None:
    os.makedirs(out_dir, exist_ok=True)
    manifest = {
        "name": os.path.basename(out_dir.rstrip("/\\")),
        "size": size,
        "fps": 12,
        "anchor": "bottom-center",
        "actions": {},
        "mood_map": MOOD_MAP,
    }
    for action, (fn, n, loop, fps) in ACTIONS.items():
        frames = fn(size, theme, n)
        for i, fr in enumerate(frames):
            fr.save(os.path.join(out_dir, f"{action}_{i:02d}.png"))
        manifest["actions"][action] = {"frames": len(frames), "loop": loop, "fps": fps}
        print(f"  {action}: {len(frames)} 帧")
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"已生成立绘包 → {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=140)
    ap.add_argument("--theme", default="pink", choices=list(THEMES.keys()))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = args.out or os.path.join(root, "assets", "sprites", "default")
    print(f"生成立绘（size={args.size}, theme={args.theme}）…")
    generate(args.size, out, args.theme)


if __name__ == "__main__":
    main()
