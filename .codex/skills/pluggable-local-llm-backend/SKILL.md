---
name: pluggable-local-llm-backend
description: Build a swappable local-LLM brain with an ordered fallback chain (Ollama -> local transformers -> template) that degrades gracefully and loads in the background. Use when adding local AI to a desktop/offline app, supporting multiple inference engines, loading transformers 5.x models, calling Ollama from stdlib, or needing the app to stay responsive while a model warms up.
keywords: [local LLM, Ollama, transformers, Qwen3, fallback chain, backend selection, dtype, device_map, accelerate, think, num_predict, /api/chat, background warmup, BrainWorker, graceful degradation]
---

# Pluggable local-LLM backend with graceful fallback

## Architecture: interface + ordered chain + factory

- One `Brain` interface: `warmup()`, `generate(req) -> reply`, `ready: bool`,
  `load_error`, `close()`. **Never raise from `warmup()`** — record `load_error`, set
  `ready=False`.
- A `HybridBrain` holds an **ordered list of backends** + a zero-dependency template
  fallback. `generate()` tries each ready backend in order; on empty/exception it falls
  through to the next, finally to the template. The app is therefore never dead.
- `create_brain(cfg)` builds the list from a `backend` config value:
  `auto -> [ollama, transformers]`, `ollama -> [ollama]`, etc. Construction is wrapped in
  try/except so a missing import never blocks startup.

```python
def generate(self, req):
    for b in self._backends:
        if not getattr(b, "ready", False): continue
        try:
            r = b.generate(req)
            if r and r.text.strip(): return r
        except Exception as e:
            log.warning("backend %s failed, falling through: %s", b.name, e)
    return self._template.generate(req)
```

## Keep the UI responsive: warm up in a background thread

Run `brain.warmup()` (weights load / service probe) on a worker thread; serve the
template instantly until a real backend flips `ready=True`. Use a queue + request
sequence number and only accept the latest in-flight result (drop stale ones).

## transformers 5.x gotchas (loading Qwen3 / new archs)

- Use **`dtype=`**, NOT the deprecated `torch_dtype=`. Wrap with a `TypeError` retry to
  stay compatible with older versions.
- Use **`.to("cuda")`**, NOT `device_map=` — `device_map` pulls in **accelerate**, which
  may be absent. `.to()` needs no extra dep.
- New architectures (e.g. `qwen3_5`) require a **recent transformers**; an old version
  errors `does not recognize this architecture`. That's the trigger to fall back.

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
want_cuda = torch.cuda.is_available()
dtype = torch.float16 if want_cuda else torch.float32
try:
    m = AutoModelForCausalLM.from_pretrained(path, dtype=dtype, trust_remote_code=True, low_cpu_mem_usage=True)
except TypeError as e:                               # old transformers
    if "dtype" not in str(e): raise
    m = AutoModelForCausalLM.from_pretrained(path, torch_dtype=dtype, trust_remote_code=True, low_cpu_mem_usage=True)
m = m.to("cuda" if want_cuda else "cpu").eval()
```

## Ollama backend in pure stdlib (urllib, no deps)

- `warmup()`: GET `/api/tags`; if connection refused → `load_error="not running"`,
  `ready=False`; if the model isn't listed → `load_error="model not pulled"`.
- `generate()`: POST `/api/chat` with `stream:false`; raise on error so the chain falls
  through.

### CRITICAL: qwen3 is a thinking model — set `"think": false`

By default qwen3 (incl. `qwen3:0.6b`) spends all `num_predict` tokens inside `<think>…</think>`
and returns **empty `content`** → you'd fall back forever and wonder why. Send
`"think": false` in the request body; also defensively fall back to the `thinking` field
if `content` is empty.

```python
body = {"model": model, "messages": msgs, "stream": False, "think": False,
        "options": {"num_predict": 80, "temperature": 0.85, "top_p": 0.9}}
resp = post_json("/api/chat", body)
text = (resp.get("message") or {}).get("content") or (resp.get("message") or {}).get("thinking") or ""
```

## Output post-processing (shared across backends)

Strip `<think>…</think>`, role prefixes, **emoji** (CJK fonts can't render them — see
`tkinter-cjk-pillow-rendering`), and truncate to 1–2 sentences. Factor `build_messages()`
(system persona + per-trigger user prompt) and `clean_reply()` into shared modules so
every backend reuses them.

## Picking the right wheel / model

- RTX 50-series (Blackwell, sm_120) needs **torch cu128** on Windows — `cu124` errors
  "sm_120 not compatible". (See `windows-oneclick-installer`.)
- The Ollama model **tag** ≠ a local safetensors dir name. Pull a known-good small tag
  (`qwen3:0.6b`) at install time and write the exact tag into config; don't hardcode a tag
  that may not exist in the Ollama library.

> Reference: `dolores/brain/{base,factory,transformers_brain,ollama_brain,prompts,postprocess}.py`.
