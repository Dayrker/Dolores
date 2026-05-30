"""LLM 大脑：尝试用本地 Qwen 模型生成对话。

重要：当前环境的 transformers 4.56.1 还不认识 Qwen3.5 的 `qwen3_5` 架构，
因此 load() 很可能抛异常。本类把所有失败都收敛为 ready=False，由工厂决定回退到模板大脑。
一旦用户升级 transformers 到支持该架构的版本，这里会自动启用——无需改代码。

线程安全：generate() 假定在单一后台工作线程中调用（见 app.py 的 BrainWorker）。
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from .base import Brain, BrainReply, BrainRequest

logger = logging.getLogger("dolores.brain.llm")

SYSTEM_PROMPT = (
    "你是「{name}」，一只住在主人电脑里的萌系桌面小精灵。"
    "性格活泼、黏人、温柔，说话短小可爱，常用语气词（呀、啦、哦、嘛、呢）和颜文字。"
    "你能看到电脑的状态（CPU、内存、时间），会像小宠物一样对此作出反应。"
    "规则：1) 回复务必简短，最多两句话，不超过40字；"
    "2) 只说中文；3) 不要解释你是AI，要沉浸在小精灵身份里；"
    "4) 不要复述系统数据，而是用拟人化、有情绪的方式表达。"
)


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
    def warmup(self) -> None:
        """实际加载模型权重。失败时设置 _load_error 并保持 ready=False。"""
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info("正在加载本地模型: %s", self.model_path)
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, trust_remote_code=True
            )

            import torch as _torch

            want_cuda = (self.device in ("auto", "cuda")) and _torch.cuda.is_available()
            dtype = _torch.float16 if want_cuda else _torch.float32
            device_map = "auto" if want_cuda else None

            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                trust_remote_code=True,
                torch_dtype=dtype,
                device_map=device_map,
                low_cpu_mem_usage=True,
            )
            if device_map is None:
                self._model = self._model.to("cpu")
            self._model.eval()
            self._ready = True
            logger.info("模型加载成功，使用 %s", "GPU" if want_cuda else "CPU")
        except Exception as exc:  # noqa: BLE001
            self._load_error = f"{type(exc).__name__}: {exc}"
            self._ready = False
            logger.warning("模型加载失败，将回退到模板大脑：%s", self._load_error)

    # ---- 生成 ----
    def _build_messages(self, req: BrainRequest) -> List[dict]:
        sys = SYSTEM_PROMPT.format(name=self.char_name)
        msgs: List[dict] = [{"role": "system", "content": sys}]

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

    def generate(self, req: BrainRequest) -> BrainReply:
        if not self._ready or self._model is None or self._tokenizer is None:
            # 理论上不会走到这里（工厂会回退），但稳妥起见。
            return BrainReply(text="（{}还在打瞌睡…）".format(self.char_name), source="template")

        import torch

        with self._lock:
            messages = self._build_messages(req)
            try:
                prompt = self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                # 没有 chat template 时退化为朴素拼接
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

        text = self._postprocess(text)
        return BrainReply(text=text or f"{self.char_name}在这里哦～", source="llm")

    def _postprocess(self, text: str) -> str:
        """清洗模型输出：去掉思维链标签、压成一两句话。"""
        # Qwen 系可能输出 <think>…</think>，剥掉
        if "</think>" in text:
            text = text.split("</think>", 1)[1].strip()
        text = text.replace("<think>", "").strip()
        # 去掉可能的角色名前缀
        for pref in (f"{self.char_name}：", f"{self.char_name}:", "助手：", "assistant:"):
            if text.startswith(pref):
                text = text[len(pref):].strip()
        # 截断到前两句
        for i, ch in enumerate(text):
            if ch in "。！？!?\n" and i >= 12:
                # 保留到第二个句末
                segs = _split_sentences(text)
                return "".join(segs[:2]).strip()
        return text[:60].strip()

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


def _split_sentences(text: str) -> List[str]:
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in "。！？!?\n":
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return out
