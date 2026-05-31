import sys
sys.path.insert(0, r"D:\Linux\Dolores")
# Windows 控制台默认 GBK，强制 stdout 用 UTF-8，避免打印 emoji/中文崩溃（仅测试用）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import copy
from dolores.config import load_config, Config
from dolores.brain import create_brain, BrainRequest

d = load_config().as_dict()
d["model"]["backend"] = "ollama"
d["model"]["ollama"]["model"] = "qwen3:0.6b"
cfg = Config(d)

b = create_brain(cfg)
print("backends:", [x.name for x in b._backends])
b.warmup()
print("status:", b.status)
for kind, kw in [("greeting", {}), ("event", {"event": "cpu_very_high"}), ("chat", {"user_text": "今天有点累"})]:
    r = b.generate(BrainRequest(kind=kind, mood="happy",
                                system_summary="CPU占用95%、内存占用40%、现在14点", **kw))
    # 避免控制台编码问题，输出 ascii 安全形式 + 长度
    safe = r.text.encode("unicode_escape").decode("ascii")
    print(f"[{kind}] src={r.source} len={len(r.text)} :: {safe}")
b.close()
print("OLLAMA-BACKEND-OK")
