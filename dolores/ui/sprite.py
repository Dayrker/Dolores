"""立绘：用 Pillow 程序化绘制一只萌萌的小精灵（不依赖任何美术素材）。

Dolores 是一团软软的水滴形小精灵，会根据情绪换表情、有腮红和高光。
每种情绪生成一张 RGBA 图，外加轻微的上下浮动动画帧。
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Dict, Tuple

from PIL import Image, ImageDraw

# 主题配色
THEMES: Dict[str, Dict[str, Tuple[int, int, int, int]]] = {
    "pink": {
        "body": (255, 209, 220, 255),
        "body_edge": (247, 168, 196, 255),
        "shade": (250, 188, 208, 255),
        "blush": (255, 150, 170, 140),
        "eye": (90, 60, 80, 255),
        "mouth": (180, 90, 110, 255),
        "highlight": (255, 255, 255, 200),
    },
    "blue": {
        "body": (197, 224, 255, 255),
        "body_edge": (150, 195, 245, 255),
        "shade": (175, 210, 250, 255),
        "blush": (160, 200, 255, 140),
        "eye": (60, 70, 100, 255),
        "mouth": (90, 120, 170, 255),
        "highlight": (255, 255, 255, 210),
    },
}


def _eyes(d: ImageDraw.ImageDraw, cx: int, cy: int, s: float, mood: str, c) -> None:
    """根据情绪画眼睛。s 为整体缩放因子，cx/cy 为脸中心。"""
    eye = c["eye"]
    ex = int(22 * s)   # 双眼水平间距的一半
    ey = int(6 * s)    # 眼睛相对脸心的垂直偏移
    r = int(7 * s)     # 眼睛半径
    lx, rx = cx - ex, cx + ex
    yy = cy - ey

    def dot(x, y, rr):
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=eye)

    def hi(x, y):
        rr = max(1, int(r * 0.32))
        d.ellipse([x - rr - int(r*0.25), y - rr - int(r*0.25),
                   x + rr - int(r*0.25), y + rr - int(r*0.25)], fill=(255, 255, 255, 230))

    if mood in ("sleepy",):
        for x in (lx, rx):
            d.arc([x - r, yy - r, x + r, yy + r], 200, 340, fill=eye, width=max(2, int(2 * s)))
    elif mood in ("happy", "comfy", "excited"):
        # 弯弯的开心眼
        for x in (lx, rx):
            d.arc([x - r, yy - r, x + r, yy + r], 200, 340, fill=eye, width=max(2, int(2.5 * s)))
        if mood == "excited":
            for x in (lx, rx):
                dot(x, yy, r); hi(x, yy)
    elif mood == "panic":
        for x in (lx, rx):
            d.ellipse([x - r, yy - r - int(s), x + r, yy + r + int(s)], outline=eye, width=max(2, int(2*s)))
            dot(x, yy, max(2, int(r * 0.5)))
    elif mood == "worried":
        for x in (lx, rx):
            dot(x, yy, r); hi(x, yy)
        # 八字眉
        d.line([lx - r, yy - r - int(4*s), lx + r, yy - r], fill=eye, width=max(1, int(1.5*s)))
        d.line([rx - r, yy - r, rx + r, yy - r - int(4*s)], fill=eye, width=max(1, int(1.5*s)))
    elif mood == "curious":
        dot(lx, yy, r); hi(lx, yy)
        d.arc([rx - r, yy - r, rx + r, yy + r], 200, 340, fill=eye, width=max(2, int(2*s)))
    else:  # lonely / default
        for x in (lx, rx):
            dot(x, yy, r); hi(x, yy)


def _mouth(d: ImageDraw.ImageDraw, cx: int, cy: int, s: float, mood: str, c) -> None:
    m = c["mouth"]
    my = cy + int(16 * s)
    w = int(10 * s)
    if mood in ("happy", "comfy"):
        d.arc([cx - w, my - w, cx + w, my + w], 20, 160, fill=m, width=max(2, int(2.2 * s)))
    elif mood == "excited":
        d.ellipse([cx - w, my - int(2*s), cx + w, my + w + int(4*s)], fill=m)
    elif mood == "panic":
        d.ellipse([cx - int(w*0.7), my - int(2*s), cx + int(w*0.7), my + w], fill=m)
    elif mood in ("worried", "lonely"):
        d.arc([cx - w, my, cx + w, my + w + int(6*s)], 200, 340, fill=m, width=max(2, int(2*s)))
    elif mood == "sleepy":
        d.arc([cx - int(w*0.5), my, cx + int(w*0.5), my + int(4*s)], 0, 180, fill=m, width=max(1, int(1.5*s)))
    else:
        d.arc([cx - w, my - w, cx + w, my + w], 30, 150, fill=m, width=max(2, int(2 * s)))


@lru_cache(maxsize=64)
def render_sprite(mood: str, size: int = 140, theme: str = "pink") -> Image.Image:
    """渲染某情绪下的小精灵立绘（带缓存）。返回正方形 RGBA 图。"""
    c = THEMES.get(theme, THEMES["pink"])
    # 超采样抗锯齿
    ss = 3
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = ss * (size / 140.0)  # 绘制缩放因子

    cx, cy = S // 2, int(S * 0.52)
    # 身体：水滴/圆球形
    bw, bh = int(S * 0.74), int(S * 0.70)
    body_box = [cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2]
    # 阴影底
    d.ellipse([cx - bw // 2 + int(6*s), cy - bh // 2 + int(10*s),
               cx + bw // 2 + int(6*s), cy + bh // 2 + int(10*s)], fill=c["shade"])
    d.ellipse(body_box, fill=c["body"], outline=c["body_edge"], width=max(2, int(3 * s)))

    # 头顶呆毛
    th = int(S * 0.12)
    d.line([cx, body_box[1] - th, cx - int(6*s), body_box[1] + int(4*s)],
           fill=c["body_edge"], width=max(2, int(3*s)))
    d.line([cx, body_box[1] - th, cx + int(8*s), body_box[1] + int(2*s)],
           fill=c["body_edge"], width=max(2, int(3*s)))

    # 高光
    d.ellipse([cx - int(bw*0.28), cy - int(bh*0.30),
               cx - int(bw*0.28) + int(22*s), cy - int(bh*0.30) + int(26*s)],
              fill=c["highlight"])

    # 腮红
    bl = c["blush"]
    br = int(10 * s)
    for sx in (-1, 1):
        bx = cx + sx * int(30 * s)
        d.ellipse([bx - br, cy + int(6*s) - int(br*0.7),
                   bx + br, cy + int(6*s) + int(br*0.7)], fill=bl)

    # 表情
    _eyes(d, cx, cy, s, mood, c)
    _mouth(d, cx, cy, s, mood, c)

    # 缩回目标尺寸
    return img.resize((size, size), Image.LANCZOS)


def render_frame(mood: str, size: int, theme: str, phase: float) -> Image.Image:
    """生成一帧带浮动动画的立绘。phase∈[0,1)，整体上下轻微浮动。"""
    base = render_sprite(mood, size, theme)
    bob = int(round(3 * math.sin(phase * 2 * math.pi)))  # 上下 ±3px
    canvas = Image.new("RGBA", (size, size + 8), (0, 0, 0, 0))
    canvas.alpha_composite(base, (0, 4 + bob))
    return canvas
