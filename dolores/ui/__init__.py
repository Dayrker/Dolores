"""Dolores 的 tkinter UI 子系统（文字与立绘均经 Pillow 渲染）。"""
from .bubble import Bubble
from .chat_input import ChatInput
from .pet_window import PetWindow

__all__ = ["PetWindow", "Bubble", "ChatInput"]
