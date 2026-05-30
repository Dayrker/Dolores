"""主角窗口：无边框、置顶、可拖拽的小精灵立绘，带浮动动画。

承载对话气泡与手动输入框。对外暴露简单接口：
- set_mood(mood)：切换表情
- say(text)：弹出气泡
- 各种回调：on_click / on_request_chat / on_quit
由于 conda Tk 无 Xft / 无 -transparentcolor，立绘窗用 -alpha，整窗背景设为接近的浅色。
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from PIL import ImageTk

from . import sprite as sprite_mod
from .bubble import Bubble
from .chat_input import ChatInput

# 立绘窗背景色（因无法做纯透明，用一个柔和的接近白来弱化方框感）
_BG = "#fdf4f8"


class PetWindow:
    def __init__(self, root: tk.Tk, cfg):
        self.root = root
        self.cfg = cfg
        self.size = cfg.get("ui.pet_size", 140)
        self.theme = cfg.get("ui.theme", "pink")
        self.margin = cfg.get("ui.margin", 24)

        self.mood = "happy"
        self._phase = 0.0
        self._anim_running = True
        self._photo: Optional[ImageTk.PhotoImage] = None

        # 回调（由 app 注入）
        self.on_request_chat: Callable[[], None] = lambda: None
        self.on_poke: Callable[[], None] = lambda: None
        self.on_quit: Callable[[], None] = lambda: None

        # 主窗
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", bool(cfg.get("ui.topmost", True)))
        try:
            self.root.attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        self.root.configure(bg=_BG)

        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size + 8,
            bg=_BG,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.pack()
        self._img_id = self.canvas.create_image(self.size // 2, (self.size + 8) // 2)

        # 子窗
        self.bubble = Bubble(
            self.root,
            max_chars=cfg.get("ui.bubble_max_chars", 40),
            theme=self.theme,
        )
        self.chat = ChatInput(self.root, on_submit=self._on_chat_submit)

        self._bind_events()
        self._place_initial()
        self._render_sprite()
        self._animate()

    # ---- 布局 ----
    def _place_initial(self) -> None:
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = self.size
        h = self.size + 8
        corner = self.cfg.get("ui.start_corner", "bottom-right")
        m = self.margin
        if corner == "bottom-right":
            x, y = sw - w - m, sh - h - m - 40
        elif corner == "bottom-left":
            x, y = m, sh - h - m - 40
        elif corner == "top-right":
            x, y = sw - w - m, m
        else:
            x, y = m, m
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ---- 事件 ----
    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double)
        self.canvas.bind("<Button-3>", self._show_menu)
        self._drag = {"x": 0, "y": 0, "moved": False}

        # 右键菜单
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="对朵拉说话…", command=lambda: self.on_request_chat())
        self.menu.add_command(label="戳一戳", command=lambda: self.on_poke())
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=lambda: self.on_quit())

    def _on_press(self, e) -> None:
        self._drag = {"x": e.x_root, "y": e.y_root, "moved": False,
                      "ox": self.root.winfo_x(), "oy": self.root.winfo_y()}

    def _on_drag(self, e) -> None:
        dx = e.x_root - self._drag["x"]
        dy = e.y_root - self._drag["y"]
        if abs(dx) > 3 or abs(dy) > 3:
            self._drag["moved"] = True
        self.root.geometry(f"+{self._drag['ox'] + dx}+{self._drag['oy'] + dy}")
        if self.bubble.visible:
            self.bubble.hide()

    def _on_release(self, e) -> None:
        if not self._drag["moved"]:
            self.on_poke()  # 单击 = 戳一戳

    def _on_double(self, e) -> None:
        self.on_request_chat()

    def _show_menu(self, e) -> None:
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _on_chat_submit(self, text: str) -> None:
        self._chat_submit_cb(text)

    # app 注入真正的处理函数
    _chat_submit_cb: Callable[[str], None] = lambda self, t: None

    def set_chat_handler(self, cb: Callable[[str], None]) -> None:
        self._chat_submit_cb = cb

    # ---- 立绘渲染与动画 ----
    def _render_sprite(self) -> None:
        frame = sprite_mod.render_frame(self.mood, self.size, self.theme, self._phase)
        self._photo = ImageTk.PhotoImage(frame)
        self.canvas.itemconfigure(self._img_id, image=self._photo)

    def _animate(self) -> None:
        if not self._anim_running:
            return
        self._phase = (self._phase + 0.04) % 1.0
        self._render_sprite()
        self.root.after(60, self._animate)

    # ---- 对外接口 ----
    def set_mood(self, mood: str) -> None:
        if mood and mood != self.mood:
            self.mood = mood
            self._render_sprite()

    def say(self, text: str, duration_ms: Optional[int] = None) -> None:
        if duration_ms is None:
            duration_ms = self.cfg.get("ui.bubble_duration_ms", 6500)
        # 气泡尾巴尖指向立绘顶部中心
        x = self.root.winfo_x() + self.size // 2
        y = self.root.winfo_y() + 6
        self.bubble.show(text, x, y, duration_ms=duration_ms)

    def open_chat(self) -> None:
        self.chat.show()

    def stop(self) -> None:
        self._anim_running = False
