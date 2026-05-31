"""大脑抽象层：定义统一接口，让模板大脑与 LLM 大脑可互换。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BrainRequest:
    """一次生成请求。"""

    # 触发类型：'chat'(用户输入) / 'autonomy'(自发) / 'event'(状态事件) / 'greeting'
    kind: str = "chat"
    user_text: str = ""            # 用户手动输入（chat 时）
    mood: str = "happy"            # 当前情绪
    event: str = ""               # 事件标识，如 'cpu_very_high'
    system_summary: str = ""       # 系统状态一行摘要
    history: List[Dict[str, str]] = field(default_factory=list)  # [{role,content}]
    context: Dict[str, str] = field(default_factory=dict)        # 额外上下文


@dataclass
class BrainReply:
    """一次生成结果。"""

    text: str
    mood: Optional[str] = None     # 大脑可建议切换到的情绪
    source: str = "template"       # 'template' | 'llm'


class Brain:
    """所有大脑的基类。"""

    name = "base"

    @property
    def ready(self) -> bool:
        """是否已就绪可生成。"""
        return True

    def generate(self, req: BrainRequest) -> BrainReply:  # noqa: D401
        raise NotImplementedError

    def warmup(self) -> None:
        """可选：预热（加载权重等）。默认空实现。"""
        return None

    def close(self) -> None:
        """可选：释放资源。"""
        return None
