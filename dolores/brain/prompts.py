"""大脑共用的提示词与消息构造。

把人设系统提示与「按触发类型构造对话消息」的逻辑集中在这里，
供 TransformersBrain / OllamaBrain 等所有 LLM 后端复用，避免重复。
"""
from __future__ import annotations

from typing import Dict, List

from .base import BrainRequest

SYSTEM_PROMPT = (
    "你是「{name}」，一只住在主人电脑里的萌系桌面小精灵。"
    "性格活泼、黏人、温柔，说话短小可爱，常用语气词（呀、啦、哦、嘛、呢）。"
    "你能看到电脑的状态（CPU、内存、时间），会像小宠物一样对此作出反应。"
    "规则：1) 回复务必简短，最多两句话，不超过40字；"
    "2) 只说中文，不要用 emoji 表情符号；"
    "3) 不要解释你是AI，要沉浸在小精灵身份里；"
    "4) 不要复述系统数据，而是用拟人化、有情绪的方式表达。"
)


def build_messages(req: BrainRequest, char_name: str) -> List[Dict[str, str]]:
    """根据请求类型构造 [{role, content}] 消息列表。"""
    sys = SYSTEM_PROMPT.format(name=char_name)
    msgs: List[Dict[str, str]] = [{"role": "system", "content": sys}]

    # 注入近期对话历史（限长）
    for turn in (req.history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})

    # 构造本轮 user 提示
    if req.kind == "chat":
        user = req.user_text or "（主人戳了戳你）"
    elif req.kind == "greeting":
        user = f"[系统] 你刚刚启动上线。电脑状态：{req.system_summary}。请向主人打个可爱的招呼。"
    elif req.kind == "event":
        user = (
            f"[系统] 检测到事件「{req.event}」。电脑状态：{req.system_summary}。"
            f"请以小精灵的身份对此作出一句可爱反应。"
        )
    else:  # autonomy
        user = (
            f"[系统] 现在没人和你说话。电脑状态：{req.system_summary}，"
            f"你的心情是「{req.mood}」。请自发地说一句萌萌的话。"
        )
    msgs.append({"role": "user", "content": user})
    return msgs
