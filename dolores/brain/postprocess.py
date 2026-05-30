"""LLM 输出后处理：清洗思维链、去前缀、压成一两句、去 emoji。"""
from __future__ import annotations

import re
from typing import List

# 常见 emoji / 杂符号区段（中文字体多半无字形，且与萌系基调不符）
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # 杂项符号与图形 / 表情
    "\U00002600-\U000027BF"   # 杂项符号 + Dingbats
    "\U0001F1E6-\U0001F1FF"   # 区域旗帜
    "\U0000FE00-\U0000FE0F"   # 变体选择符
    "\U00002190-\U000021FF"   # 箭头
    "\U00002B00-\U00002BFF"   # 杂项符号与箭头
    "]+",
    flags=re.UNICODE,
)


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text)


def split_sentences(text: str) -> List[str]:
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in "。！？!?\n":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out


def clean_reply(text: str, char_name: str = "Dolores", max_chars: int = 60) -> str:
    """把模型原始输出清洗成一段简短可爱的中文。"""
    if not text:
        return ""
    # 剥离思维链
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.replace("<think>", "").strip()
    # 去角色名/助手前缀
    for pref in (f"{char_name}：", f"{char_name}:", "助手：", "assistant:", "Assistant:"):
        if text.startswith(pref):
            text = text[len(pref):].strip()
    # 去 emoji
    text = strip_emoji(text).strip()
    # 压到前两句
    segs = split_sentences(text)
    if len(segs) > 2 and len("".join(segs[:2])) >= 8:
        text = "".join(segs[:2]).strip()
    return text[:max_chars].strip()
