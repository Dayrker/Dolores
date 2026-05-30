"""Ollama 大脑：通过本地 Ollama HTTP 服务推理（备选后端）。

仅用标准库 urllib，无需新依赖。默认连 http://127.0.0.1:11434。
服务未启动 / 模型未拉取时，warmup() 把原因记到 _load_error 并保持 ready=False，
由 HybridBrain 回退到下一后端。
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Optional

from .base import Brain, BrainReply, BrainRequest
from .postprocess import clean_reply
from .prompts import build_messages

logger = logging.getLogger("dolores.brain.ollama")


class OllamaBrain(Brain):
    """Ollama 推理后端。"""

    name = "ollama"

    def __init__(
        self,
        model: str,
        host: str = "http://127.0.0.1:11434",
        char_name: str = "Dolores",
        max_new_tokens: int = 80,
        temperature: float = 0.85,
        top_p: float = 0.9,
        keep_alive: str = "5m",
        request_timeout: int = 60,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.char_name = char_name
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.keep_alive = keep_alive
        self.request_timeout = request_timeout

        self._ready = False
        self._load_error: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    # ---- HTTP 工具 ----
    def _get_json(self, path: str, timeout: float):
        req = urllib.request.Request(self.host + path, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict, timeout: float):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.host + path, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ---- 探测 ----
    def warmup(self) -> None:
        """检查 Ollama 是否在线、目标模型是否已拉取。"""
        try:
            tags = self._get_json("/api/tags", timeout=2.5)
            names = {m.get("name", "") for m in tags.get("models", [])}
            # 允许带/不带 :tag 的匹配
            base = self.model.split(":")[0]
            matched = any(n == self.model or n.split(":")[0] == base for n in names)
            if not names:
                self._ready = True  # 服务在，但无模型列表时仍尝试（生成时再报错）
                logger.info("Ollama 在线（模型列表为空，将在生成时校验）")
            elif matched:
                self._ready = True
                logger.info("Ollama 在线，模型 %s 可用", self.model)
            else:
                self._ready = False
                self._load_error = f"模型 '{self.model}' 未拉取（ollama pull {self.model}）"
                logger.info(self._load_error)
        except urllib.error.URLError as exc:
            self._ready = False
            self._load_error = f"Ollama 未运行（{self.host}）：{exc.reason}"
            logger.info(self._load_error)
        except Exception as exc:  # noqa: BLE001
            self._ready = False
            self._load_error = f"{type(exc).__name__}: {exc}"
            logger.info("Ollama 探测失败：%s", self._load_error)

    # ---- 生成 ----
    def generate(self, req: BrainRequest) -> BrainReply:
        messages = build_messages(req, self.char_name)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": self.max_new_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
            },
        }
        with self._lock:
            # 出错时抛异常，交给 HybridBrain 回退
            resp = self._post_json("/api/chat", payload, timeout=self.request_timeout)
        text = (resp.get("message") or {}).get("content", "")
        text = clean_reply(text, self.char_name)
        return BrainReply(text=text or f"{self.char_name}在这里哦～", source="ollama")

    def close(self) -> None:
        # 尝试卸载模型释放显存（失败无所谓）
        try:
            self._post_json(
                "/api/chat",
                {"model": self.model, "messages": [], "keep_alive": 0},
                timeout=3,
            )
        except Exception:
            pass
