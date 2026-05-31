"""手动指令输入框：让用户主动和 Dolores 聊天 / 下指令。

难点：conda Tk 的 Entry 能正确「存储」中文（.get() 拿到真 Unicode），但「显示」是豆腐块。
方案：用一个隐藏的 Entry 捕获按键，再用 Pillow 实时把当前输入内容渲染成预览图显示。
回车提交，Esc 关闭。
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageTk

from . import text_renderer as tr


class ChatInput:
    """悬浮输入条。回调 on_submit(text) 在用户回车时触发。"""

    def __init__(
        self,
        master: tk.Misc,
        on_submit: Callable[[str], None],
        width: int = 300,
        placeholder: str = "和朵拉说点什么…（回车发送，Esc 关闭）",
    ):
        self.master = master
        self.on_submit = on_submit
        self.width = width
        self.placeholder = placeholder

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.98)
        except tk.TclError:
            pass
        self.win.withdraw()

        # 预览图标签
        self.preview = tk.Label(self.win, bd=0, highlightthickness=0, bg="#fffdfe")
        self.preview.pack()

        # 隐藏的 Entry，仅用于捕获键入（StringVar 跟踪变化）
        self.var = tk.StringVar()
        self.entry = tk.Entry(self.win, textvariable=self.var)
        # 不 pack → 不显示；但需要存在于窗口里才能获得焦点
        self.entry.place(x=-1000, y=-1000)
        self.var.trace_add("write", lambda *_: self._refresh())

        self.entry.bind("<Return>", self._submit)
        self.entry.bind("<KP_Enter>", self._submit)
        self.entry.bind("<Escape>", lambda e: self.hide())

        self._photo: Optional[ImageTk.PhotoImage] = None
        self._visible = False

    def _render(self, text: str) -> Image.Image:
        show = text if text else self.placeholder
        color = (70, 50, 85, 255) if text else (170, 150, 165, 255)
        text_img = tr.render_text(show, size=16, color=color, max_width=self.width - 28)
        tw, th = text_img.size
        w = self.width
        h = th + 20
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(
            [1, 1, w - 2, h - 2], radius=14, fill=(255, 253, 254, 255),
            outline=(247, 168, 196, 255), width=2,
        )
        # 左侧小图标
        d.text((10, h // 2 - 8), ">", fill=(247, 168, 196, 255))
        img.alpha_composite(text_img, (24, 10))
        return img

    def _refresh(self) -> None:
        img = self._render(self.var.get())
        self._photo = ImageTk.PhotoImage(img)
        self.preview.configure(image=self._photo)
        self.win.update_idletasks()
        # 重新定位以适应高度变化
        self._reposition(img.size)

    def _reposition(self, size) -> None:
        w, h = size
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = (sw - w) // 2
        y = sh - h - 80
        self.win.geometry(f"{w}x{h}+{x}+{y}")

    def show(self) -> None:
        self.var.set("")
        self._refresh()
        self.win.deiconify()
        self.win.lift()
        self.entry.focus_force()
        self._visible = True

    def hide(self) -> None:
        self._visible = False
        try:
            self.win.withdraw()
        except tk.TclError:
            pass

    def toggle(self) -> None:
        self.hide() if self._visible else self.show()

    def _submit(self, _event=None) -> None:
        text = self.var.get().strip()
        self.var.set("")
        self.hide()
        if text:
            self.on_submit(text)

    @property
    def visible(self) -> bool:
        return self._visible

    def destroy(self) -> None:
        try:
            self.win.destroy()
        except Exception:
            pass
