# .codex — 可复用经验技能库（Skills）

本目录汇集 **Dolores 桌面萌宠**项目从 0→1 及后续跨平台改造中沉淀的、**可迁移复用**的
工程经验。每条 Skill 都源自真实踩坑与已验证的解决方案，配有可直接套用的代码片段，并指向
本仓库的参考实现。

> 约定：每个 Skill 一个目录，内含 `SKILL.md`，带 `name` / `description` / `keywords`
> frontmatter，便于按场景检索。

## Skills 一览

| Skill | 何时用 |
|-------|--------|
| [tkinter-cjk-pillow-rendering](skills/tkinter-cjk-pillow-rendering/SKILL.md) | tkinter 显示中文/emoji 变成豆腐块 □；conda Tk 无 Xft（`font families` 只有 `('fixed',)`）；需要跨平台稳定显示非 ASCII 文本 |
| [cross-platform-system-metrics](skills/cross-platform-system-metrics/SKILL.md) | 不用 psutil 读 CPU%/内存/负载；同时支持 Linux `/proc` 与原生 Windows（ctypes 调 Win32） |
| [pluggable-local-llm-backend](skills/pluggable-local-llm-backend/SKILL.md) | 给桌面/离线应用接本地大模型；多推理引擎切换 + 优雅回退；transformers 5.x 加载坑；stdlib 调 Ollama（含 qwen3 `think` 坑） |
| [windows-oneclick-installer](skills/windows-oneclick-installer/SKILL.md) | 把 WSL 开发的 Python 应用做成 Windows 双击一键安装（winget 装 Python、建 venv、复制 WSL 模型、桌面快捷方式、UTF-8 BOM、cu128 等） |
| [desktop-pet-architecture](skills/desktop-pet-architecture/SKILL.md) | 做桌面宠物/常驻陪伴体；感知→情绪→自主→大脑→UI 分层；tkinter 主线程 + 后台推理；图片/矢量可换立绘动画系统 |

## 核心教训速查（最容易再次踩到的）

- **conda Tk 无 Xft** → 中文只能用 **Pillow 画成图**再贴；`-transparentcolor` 在 X11 不支持，只能 `-alpha`。
- **WSL 代理常常只对 Windows 生效**，WSL 自身联不上 → 联网安装放到 Windows 侧做。
- **WSL 内的模型符号链接 Windows 读不到** → 安装时 `cp -L` 解引用复制到真实目录。
- **PowerShell 5.1 必须 UTF-8 BOM** 才能正确解析中文脚本。
- **Windows 默认 `python.exe` 是应用商店占位**，要排除 `WindowsApps` 路径并 winget 装真 Python。
- **RTX 50 系（sm_120）torch 要 cu128**，cu124 不兼容。
- **transformers 5.x**：用 `dtype=`（非 `torch_dtype=`）、`.to('cuda')`（非 `device_map=`，免 accelerate）。
- **qwen3 是思考模型**：Ollama 请求要带 `"think": false`，否则 `content` 为空。
- **字体缺字形检测**：`getbbox()` 不可靠（.notdef 也有 bbox），要和 .notdef 位图比对。

## 参考实现

完整可运行代码见本仓库：`dolores/`（应用）、`windows/`（安装器）、`scripts/`（生成与自检）、
`docs/`（架构与使用）。
