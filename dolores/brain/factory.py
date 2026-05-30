"""大脑工厂：根据配置创建大脑，并实现 LLM → 模板 的优雅回退。

回退策略由 HybridBrain 承载：
- 若启用 LLM 且能成功加载 → 用 LLM 生成，单次生成异常时退回模板；
- 否则全程使用模板大脑。
模型加载放在后台（warmup），加载完成前一律用模板，保证 UI 秒开。
"""
from __future__ import annotations

import logging
import threading

from ..config import Config
from .base import Brain, BrainReply, BrainRequest
from .template_brain import TemplateBrain

logger = logging.getLogger("dolores.brain.factory")


class HybridBrain(Brain):
    """组合大脑：优先 LLM，未就绪/出错时回退模板。线程安全。"""

    name = "hybrid"

    def __init__(self, template: TemplateBrain, llm=None):
        self._template = template
        self._llm = llm  # 可能为 None
        self._llm_enabled = llm is not None
        self._warming = False
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return True  # 模板永远就绪

    @property
    def using_llm(self) -> bool:
        return bool(self._llm and getattr(self._llm, "ready", False))

    @property
    def status(self) -> str:
        if not self._llm_enabled:
            return "模板大脑（未启用模型）"
        if self._warming:
            return "模板大脑（模型加载中…）"
        if self.using_llm:
            return "本地模型大脑 ✨"
        err = getattr(self._llm, "load_error", None)
        return f"模板大脑（模型不可用：{err}）" if err else "模板大脑"

    def warmup(self) -> None:
        """后台加载 LLM；期间 generate 继续走模板。"""
        if not self._llm_enabled:
            return
        self._warming = True
        try:
            self._llm.warmup()
            if self.using_llm:
                logger.info("HybridBrain 已切换到本地模型大脑")
            else:
                logger.info("HybridBrain 保持模板大脑（模型未就绪）")
        finally:
            self._warming = False

    def generate(self, req: BrainRequest) -> BrainReply:
        if self.using_llm:
            try:
                reply = self._llm.generate(req)
                if reply and reply.text.strip():
                    return reply
                logger.debug("LLM 返回空，回退模板")
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM 生成异常，回退模板：%s", exc)
        return self._template.generate(req)

    def close(self) -> None:
        if self._llm:
            try:
                self._llm.close()
            except Exception:
                pass


def create_brain(cfg: Config) -> HybridBrain:
    """按配置创建 HybridBrain（不在此处加载权重，交给 warmup）。"""
    char_name = cfg.get("character.name", "Dolores")
    template = TemplateBrain(char_name=char_name)

    llm = None
    if cfg.get("model.enabled", True):
        try:
            from .transformers_brain import TransformersBrain

            model_path = cfg.abspath(cfg.get("model.path", "models/Qwen3.5-0.8B"))
            llm = TransformersBrain(
                model_path=model_path,
                char_name=char_name,
                device=cfg.get("model.device", "auto"),
                max_new_tokens=cfg.get("model.max_new_tokens", 80),
                temperature=cfg.get("model.temperature", 0.85),
                top_p=cfg.get("model.top_p", 0.9),
            )
        except Exception as exc:  # noqa: BLE001 —— 连 import 都失败也不影响启动
            logger.warning("无法创建 LLM 大脑（%s），仅用模板", exc)
            llm = None

    return HybridBrain(template=template, llm=llm)
