"""LLM 大脑：用本地 Qwen 模型生成对话（transformers 后端）。

transformers 5.9 已支持 Qwen3.5(qwen3_5)。注意两点（与旧版不同）：
- 用 `dtype=` 而非已废弃的 `torch_dtype=`；
- 用 `.to('cuda')` 而非 `device_map=`（后者需要 accelerate，环境未装）。
为兼容不同 transformers 版本，dtype 参数名做了回退处理。

线程安全：generate() 假定在单一后台工作线程中调用（见 app.py 的 BrainWorker）。
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from .base import Brain, BrainReply, BrainRequest
from .postprocess import clean_reply
from .prompts import build_messages

logger = logging.getLogger("dolores.brain.llm")


class TransformersBrain(Brain):
    """封装本地 HuggingFace 因果语言模型。"""

    name = "llm"

    def __init__(
        self,
        model_path: str,
        char_name: str = "Dolores",
        device: str = "auto",
        max_new_tokens: int = 80,
        temperature: float = 0.85,
        top_p: float = 0.9,
    ):
        self.model_path = model_path
        self.char_name = char_name
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p

        self._tokenizer = None
        self._model = None
        self._ready = False
        self._load_error: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    # ---- 加载 ----
    def _load_model(self, dtype, want_cuda: bool):
        """加载模型，兼容 transformers 新旧 dtype 参数名。"""
        from transformers import AutoModelForCausalLM

        common = dict(trust_remote_code=True, low_cpu_mem_usage=True)
        try:
            model = AutoModelForCausalLM.from_pretrained(self.model_path, dtype=dtype, **common)
        except TypeError as exc:
            if "dtype" not in str(exc):
                raise
            # 旧版 transformers：回退到 torch_dtype
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path, torch_dtype=dtype, **common
            )
        return model.to("cuda" if want_cuda else "cpu")

    def warmup(self) -> None:
        """实际加载模型权重。失败时设置 _load_error 并保持 ready=False。"""
        try:
            import torch
            from transformers import AutoTokenizer

            logger.info("正在加载本地模型: %s", self.model_path)
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, trust_remote_code=True
            )

            want_cuda = (self.device in ("auto", "cuda")) and torch.cuda.is_available()
            dtype = torch.float16 if want_cuda else torch.float32

            self._model = self._load_model(dtype, want_cuda)
            self._model.eval()
            self._ready = True
            logger.info("模型加载成功，使用 %s", "GPU" if want_cuda else "CPU")
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._ready = False
            logger.warning("模型加载失败，将回退到其它大脑：%s", self._load_error)

    # ---- 生成 ----
    def generate(self, req: BrainRequest) -> BrainReply:
        if not self._ready or self._model is None or self._tokenizer is None:
            return BrainReply(text="（{}还在打瞌睡…）".format(self.char_name), source="template")

        import torch

        with self._lock:
            messages = build_messages(req, self.char_name)
            try:
                prompt = self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                prompt = "\n".join(m["content"] for m in messages) + "\n"

            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
            gen_kwargs = dict(
                max_new_tokens=self.max_new_tokens,
                do_sample=True,
                temperature=self.temperature,
                top_p=self.top_p,
                pad_token_id=(
                    self._tokenizer.pad_token_id
                    if self._tokenizer.pad_token_id is not None
                    else self._tokenizer.eos_token_id
                ),
            )
            with torch.no_grad():
                out = self._model.generate(**inputs, **gen_kwargs)
            gen = out[0][inputs["input_ids"].shape[1]:]
            text = self._tokenizer.decode(gen, skip_special_tokens=True).strip()

        text = clean_reply(text, self.char_name)
        return BrainReply(text=text or f"{self.char_name}在这里哦～", source="llm")

    def close(self) -> None:
        self._model = None
        self._tokenizer = None
        self._ready = False
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
