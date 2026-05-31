"""对话气泡窗口：一个无边框、置顶的小窗，显示 Dolores 说的话。

气泡用 Pillow 画成圆角卡片图（带小尾巴），贴到独立 Toplevel 上。
支持 transparentcolor 的 Tk 后端会隐藏卡片透明角落；否则退回浅色半透明窗口。
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

from . import text_renderer as tr
from .transparency import apply_alpha_shape, apply_transparent_background


def _rounded_card(
    text_img: Image.Image,
    pad_x: int = 16,
    pad_y: int = 12,
    radius: int = 18,
    bg=(255, 252, 254, 255),
    border=(247, 168, 196, 255),
    tail: str = "bottom",
) -> Image.Image:
    """把文字图包成一张圆角对话卡片（带指向立绘的小尾巴）。"""
    tw, th = text_img.size
    tail_h = 12
    w = tw + pad_x * 2
    h = th + pad_y * 2 + tail_h
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    body_bottom = h - tail_h
    d.rounded_rectangle(
        [1, 1, w - 2, body_bottom], radius=radius, fill=bg, outline=border, width=2
    )
    # 小尾巴（朝下，指向立绘）
    cx = w // 2
    d.polygon(
        [(cx - 9, body_bottom - 1), (cx + 9, body_bottom - 1), (cx, body_bottom + tail_h - 2)],
        fill=bg,
    )
    # 补尾巴描边
    d.line([(cx - 9, body_bottom - 1), (cx, body_bottom + tail_h - 2)], fill=border, width=2)
    d.line([(cx + 9, body_bottom - 1), (cx, body_bottom + tail_h - 2)], fill=border, width=2)

    img.alpha_composite(text_img, (pad_x, pad_y))
    return img


class Bubble:
    """对话气泡，挂在主窗（pet）之上的独立 Toplevel。"""

    def __init__(self, master: tk.Misc, max_chars: int = 40, theme: str = "pink"):
        self.master = master
        self.max_width_px = max(160, max_chars * 14)
        self.theme = theme

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self._bg, self._has_chroma_transparency = apply_transparent_background(
            self.win, "#fffcfe", fallback_alpha=0.97
        )
        self.win.withdraw()

        self.label = tk.Label(self.win, bd=0, highlightthickness=0, bg=self._bg)
        self.label.pack()
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._hide_job: Optional[str] = None
        self._visible = False

    def show(self, text: str, x: int, y: int, duration_ms: int = 6500) -> None:
        """在 (x, y)（气泡尾巴尖的位置）上方显示一段话。"""
        text_img = tr.render_text(
            text, size=17, color=(70, 50, 85, 255), max_width=self.max_width_px
        )
        card = _rounded_card(text_img)
        self._photo = ImageTk.PhotoImage(card)
        self.label.configure(image=self._photo)
        self.win.update_idletasks()

        w, h = card.size
        # 让尾巴尖大致落在 (x, y)，卡片整体在其上方
        px = int(x - w / 2)
        py = int(y - h)
        # 夹在屏幕可视范围内，避免跑出右/上边缘
        sw = self.win.winfo_screenwidth()
        px = max(4, min(px, sw - w - 4))
        py = max(4, py)
        self.win.geometry(f"{w}x{h}+{px}+{py}")
        self.win.deiconify()
        self.win.lift()
        if not self._has_chroma_transparency:
            apply_alpha_shape(self.win, card)
        self._visible = True

        if self._hide_job is not None:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
        if duration_ms > 0:
            self._hide_job = self.win.after(duration_ms, self.hide)

    def hide(self) -> None:
        self._visible = False
        try:
            self.win.withdraw()
        except tk.TclError:
            pass

    @property
    def visible(self) -> bool:
        return self._visible

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except Exception:
            pass
