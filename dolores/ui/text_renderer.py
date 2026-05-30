"""文字渲染：用 Pillow 直接把中文/颜文字画成图片，绕开 conda Tk 无 Xft 的限制。

见项目记录：torch2.10 的 Tk 不支持 Xft，只能渲染 'fixed'，无法显示中文/emoji。
所有需要显示文字的地方都通过本模块拿到 PIL.Image / ImageTk.PhotoImage。
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# 候选字体路径（按优先级）。Windows 侧字体在 WSL 下可直接读。
_CJK_CANDIDATES: List[str] = [
    "/mnt/c/Windows/Fonts/msyh.ttc",       # 微软雅黑
    "/mnt/c/Windows/Fonts/msyhl.ttc",
    "/mnt/c/Windows/Fonts/simhei.ttf",     # 黑体
    "/mnt/c/Windows/Fonts/simsun.ttc",     # 宋体
    os.path.expanduser("~/.local/share/fonts/msyh.ttc"),
    os.path.expanduser("~/.local/share/fonts/simhei.ttf"),
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # 兜底（无中文但不崩）
]

_EMOJI_CANDIDATES: List[str] = [
    "/mnt/c/Windows/Fonts/seguiemj.ttf",
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
]


def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


CJK_FONT_PATH = _first_existing(_CJK_CANDIDATES)
EMOJI_FONT_PATH = _first_existing(_EMOJI_CANDIDATES)


@lru_cache(maxsize=4)
def _notdef_signature(path: str, size: int = 24) -> Optional[bytes]:
    """取该字体 .notdef（缺字形）字形的位图签名，用于识别豆腐块。"""
    try:
        f = ImageFont.truetype(path, size)
        # 一个几乎不可能存在的私用区码点 → 必为 .notdef
        return bytes(f.getmask("", mode="1"))
    except Exception:
        return None


@lru_cache(maxsize=4096)
def _renderable(ch: str) -> bool:
    """判断单个字符在中文字体里是否有真实字形（而非豆腐块）。"""
    if not CJK_FONT_PATH:
        return True  # 无从判断，放行
    if ch in " \t\n\r　" or ch == "️":
        return True
    try:
        f = ImageFont.truetype(CJK_FONT_PATH, 24)
        m = f.getmask(ch, mode="1")
        if m.getbbox() is None:
            return True  # 空白字形（如全角空格），视为可用
        notdef = _notdef_signature(CJK_FONT_PATH)
        if notdef is None:
            return True
        return bytes(m) != notdef
    except Exception:
        return True


def sanitize(text: str, replacement: str = "") -> str:
    """剔除中文字体无法渲染的字符（豆腐块预防）。

    用于 LLM 输出或任何外部文本，避免界面出现 □。颜文字常用符号大多保留。
    """
    if not text:
        return text
    out = []
    for ch in text:
        if ord(ch) < 0x80 or _renderable(ch):
            out.append(ch)
        elif replacement:
            out.append(replacement)
    return "".join(out)


@lru_cache(maxsize=64)
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """按字号取一个中文字体对象（带缓存）。找不到则用 PIL 默认位图字体。"""
    path = CJK_FONT_PATH
    if bold:
        bold_path = _first_existing(
            ["/mnt/c/Windows/Fonts/msyhbd.ttc", "/mnt/c/Windows/Fonts/simhei.ttf"]
        )
        path = bold_path or path
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def measure(text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """测量多行文本的像素宽高。"""
    dummy = Image.new("RGBA", (4, 4))
    d = ImageDraw.Draw(dummy)
    bbox = d.multiline_textbbox((0, 0), text, font=font, spacing=4)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """按像素宽度对中英文混排做自动换行（按字符粒度，适合中文）。"""
    dummy = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    lines: List[str] = []
    for paragraph in text.split("\n"):
        cur = ""
        for ch in paragraph:
            trial = cur + ch
            w = dummy.textlength(trial, font=font)
            if w > max_width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur = trial
        lines.append(cur)
    return "\n".join(lines)


def render_text(
    text: str,
    size: int = 18,
    color: Tuple[int, int, int, int] = (60, 45, 75, 255),
    bold: bool = False,
    max_width: Optional[int] = None,
    align: str = "left",
    padding: Tuple[int, int, int, int] = (0, 0, 0, 0),
    clean: bool = True,
) -> Image.Image:
    """把文字渲染成带透明背景的 RGBA 图片。clean=True 时先剔除豆腐块字符。"""
    if clean:
        text = sanitize(text) or text  # 全被剔除时退回原文，至少不空
    font = get_font(size, bold=bold)
    if max_width:
        text = wrap_text(text, font, max_width)
    w, h = measure(text, font)
    pl, pt, pr, pb = padding
    img = Image.new("RGBA", (max(1, w + pl + pr), max(1, h + pt + pb)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.multiline_text((pl, pt), text, font=font, fill=color, spacing=4, align=align)
    return img
