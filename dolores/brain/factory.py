"""大脑工厂：按配置创建大脑，并实现 多后端 → 模板 的优雅回退。

回退链由 HybridBrain 承载，按优先级依次尝试已就绪的后端，全部失败则用模板大脑。
后端选择由 config 的 `model.backend` 决定：
- "auto"        : [ollama, transformers] → template（默认）
- "ollama"      : [ollama] → template
- "transformers": [transformers] → template
- "template"    : 仅模板
模型/服务的加载放在后台 warmup，未就绪前一律用模板，保证 UI 秒开。
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from ..config import Config
from .base import Brain, BrainReply, BrainRequest
from .template_brain import TemplateBrain

logger = logging.getLogger("dolores.brain.factory")


class HybridBrain(Brain):
    """组合大脑：按顺序尝试若干 LLM 后端，全部不可用时回退模板。线程安全。"""

    name = "hybrid"

    def __init__(self, template: TemplateBrain, backends: Optional[List[Brain]] = None):
        self._template = template
        self._backends: List[Brain] = backends or []
        self._warming = False
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return True  # 模板永远就绪

    def _active_backend(self) -> Optional[Brain]:
        for b in self._backends:
            if getattr(b, "ready", False):
                return b
        return None

    @property
    def using_llm(self) -> bool:
        return self._active_backend() is not None

    @property
    def status(self) -> str:
        if not self._backends:
            return "模板大脑（未启用模型）"
        if self._warming:
            return "模板大脑（后端加载中…）"
        active = self._active_backend()
        if active is not None:
            label = {"ollama": "Ollama 大脑", "llm": "本地模型大脑"}.get(active.name, active.name)
            return f"{label} ✨"
        # 都没就绪，给出原因
        errs = []
        for b in self._backends:
            err = getattr(b, "load_error", None)
            if err:
                errs.append(f"{b.name}: {err}")
        return "模板大脑（" + ("；".join(errs) if errs else "后端不可用") + "）"

    def warmup(self) -> None:
        """后台依次加载各后端；期间 generate 继续走模板。"""
        if not self._backends:
            return
        self._warming = True
        try:
            for b in self._backends:
                try:
                    b.warmup()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("后端 %s warmup 异常：%s", b.name, exc)
            active = self._active_backend()
            if active is not None:
                logger.info("HybridBrain 启用后端：%s", active.name)
            else:
                logger.info("HybridBrain 保持模板大脑（无可用后端）")
        finally:
            self._warming = False

    def generate(self, req: BrainRequest) -> BrainReply:
        for b in self._backends:
            if not getattr(b, "ready", False):
                continue
            try:
                reply = b.generate(req)
                if reply and reply.text.strip():
                    return reply
                logger.debug("后端 %s 返回空，尝试下一个", b.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("后端 %s 生成异常，尝试下一个：%s", b.name, exc)
        return self._template.generate(req)

    def close(self) -> None:
        for b in self._backends:
            try:
                b.close()
            except Exception:
                pass


def _make_ollama(cfg: Config, char_name: str):
    from .ollama_brain import OllamaBrain

    o = cfg.section("model").get("ollama", {}) or {}
    return OllamaBrain(
        model=o.get("model", "qwen3:0.6b"),
        host=o.get("host", "http://127.0.0.1:11434"),
        char_name=char_name,
        max_new_tokens=cfg.get("model.max_new_tokens", 80),
        temperature=cfg.get("model.temperature", 0.85),
        top_p=cfg.get("model.top_p", 0.9),
        keep_alive=o.get("keep_alive", "5m"),
        request_timeout=o.get("request_timeout", 60),
    )


def _make_transformers(cfg: Config, char_name: str):
    from .transformers_brain import TransformersBrain

    model_path = cfg.abspath(cfg.get("model.path", "models/Qwen3.5-0.8B"))
    return TransformersBrain(
        model_path=model_path,
        char_name=char_name,
        device=cfg.get("model.device", "auto"),
        max_new_tokens=cfg.get("model.max_new_tokens", 80),
        temperature=cfg.get("model.temperature", 0.85),
        top_p=cfg.get("model.top_p", 0.9),
    )


def create_brain(cfg: Config) -> HybridBrain:
    """按配置创建 HybridBrain（不在此处加载权重，交给 warmup）。"""
    char_name = cfg.get("character.name", "Dolores")
    template = TemplateBrain(char_name=char_name)

    # 总开关：关掉就只用模板
    if not cfg.get("model.enabled", True):
        return HybridBrain(template=template, backends=[])

    backend = str(cfg.get("model.backend", "auto")).lower()
    order = {
        "auto": ["ollama", "transformers"],
        "ollama": ["ollama"],
        "transformers": ["transformers"],
        "template": [],
    }.get(backend, ["ollama", "transformers"])

    builders = {"ollama": _make_ollama, "transformers": _make_transformers}
    backends: List[Brain] = []
    for key in order:
        try:
            backends.append(builders[key](cfg, char_name))
        except Exception as exc:  # noqa: BLE001 —— 构造失败不影响启动
            logger.warning("无法创建后端 %s（%s），跳过", key, exc)

    return HybridBrain(template=template, backends=backends)
