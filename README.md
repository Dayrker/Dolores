# 🌸 Dolores · 桌面萌宠小精灵

> 一只住在你电脑里、会观察电脑状态、像有一点点自主意识的萌系桌面宠物。
> 支持 **Windows 一键安装**，本地 LLM 驱动（Ollama / 本地 Qwen3 任选）。

Dolores（朵拉）会安静地待在屏幕角落，用可爱的小表情陪着你。她能感知 CPU /
内存 / 时间等电脑状态，并**自发**地做出反应——CPU 飙高会惊慌、夜深了会提醒你
休息、太久没理她会撒娇。你不用一直给她下指令，但随时可以双击她、打字和她聊天。

她会蹦跶、挥手、眨眼、打瞌睡——一整套图片立绘动作，也可以换成你自己的立绘包。

---

## ✨ 特性

- **实时感知电脑状态**：CPU、内存、负载、时间段。Linux 读 `/proc`，Windows 用
  ctypes 调 Win32（均**不依赖 psutil**）。
- **情绪 + 自主行为**：情绪状态机（开心 / 悠闲 / 兴奋 / 担心 / 惊慌 / 困倦 / 寂寞），
  自主引擎决定**何时自己开口**，无需手动指令。
- **图片立绘 + 多动作**：idle / blink / bounce / wave / sleep / panic 多套动画，
  戳一戳会蹦跶、打招呼会挥手。可用自己的 PNG 立绘包替换。
- **可插拔大脑（本地优先）**：
  - **Ollama** 后端（Windows 一键安装默认）——本地推理引擎，省心。
  - **本地 Qwen3.5** 后端（transformers + GPU）——用你下载的本地权重。
  - **模板大脑**——零依赖兜底，永远在线。
  - 三者自动回退：Ollama → 本地 Qwen → 模板，任何一环不可用都不影响使用。
- **跨平台**：原生 Windows（一键安装）与 Linux/WSL 皆可运行。
- **稳定优先**：模型后台加载、UI 秒开；出错优雅降级，不崩溃。

---

## 🚀 Windows 一键安装（推荐）

1. 把整个项目放在 Windows 可访问的位置（如 `D:\Linux\Dolores`）。
2. 进入 `windows\` 文件夹，**双击 `install.bat`**。
3. 脚本会自动完成：
   - 检测/安装真正的 Python（缺失则用 winget 装 Python 3.12）
   - 创建虚拟环境 `.venv` 并安装依赖（Pillow）
   - 安装 **Ollama** 并拉取一个小巧的 Qwen 模型（默认后端）
   - 生成默认立绘、写入配置、创建**桌面快捷方式**
4. 完成后，双击桌面「**Dolores**」即可启动～

想用本地 Qwen3.5 权重（transformers + GPU）而非 Ollama：

```powershell
# 在 windows\ 目录下，右键“以 PowerShell 运行”或在终端执行：
powershell -ExecutionPolicy Bypass -File install.ps1 -Backend transformers
```
该模式会安装 GPU 版 PyTorch（RTX 50 系用 cu128）并从 WSL 复制本地模型。

> 卸载：运行 `windows\uninstall.ps1`（保留模型与配置，仅删 `.venv` 与快捷方式）。

---

## 🐧 Linux / WSL 运行

```bash
cd /mnt/d/Linux/Dolores
# 用带 torch/transformers/Pillow 的解释器（开发环境示例）：
/home/dayrker/anaconda3/envs/torch2.10/bin/python run.py
# 或
python -m dolores
```

---

## 🎮 交互方式

| 操作 | 效果 |
|------|------|
| **单击**她 | 戳一戳，她会开心地蹦跶 |
| **双击**她 | 打开聊天输入框 |
| **拖拽** | 把她拖到任意位置 |
| **右键** | 菜单：说话 / 戳一戳 / 退出 |
| 聊天框 **回车 / Esc** | 发送 / 关闭 |

---

## 🧠 大脑后端

由 `config.json` 的 `model.backend` 选择：

| 值 | 行为 |
|----|------|
| `auto`（默认） | 依次尝试 Ollama → 本地 Qwen(transformers) → 模板 |
| `ollama` | 只用 Ollama（→ 模板兜底） |
| `transformers` | 只用本地 Qwen3.5 权重（→ 模板兜底） |
| `template` | 只用内置话术，不加载任何模型 |

- **Ollama**：需本地运行 Ollama 服务（`ollama serve`）并已 `ollama pull` 对应模型；
  模型名写在 `model.ollama.model`。一键安装会自动配好。
- **本地 Qwen3.5**：权重放在 `models/Qwen3.5-0.8B`，需 `transformers≥5.x`（支持 `qwen3_5`）
  与 GPU/torch。实测 RTX 5070 Ti 上加载 ~2s、显存 ~1.6GB。

---

## 🎨 自定义立绘

立绘包在 `assets/sprites/<包名>/`，由 `manifest.json` + `<动作>_<帧号>.png` 组成：

```
assets/sprites/default/
  manifest.json
  idle_00.png idle_01.png …
  wave_00.png …  bounce_00.png …  sleep_00.png …  panic_00.png …
```

- 想换立绘：仿照 `default/` 放一套你的 PNG，在 `config.json` 把
  `ui.sprite.pack` 指过去（`ui.sprite.mode` 设 `image` 或 `auto`）。
- 重新生成内置立绘：`python scripts/generate_sprites.py`。
- `manifest.json` 里 `actions` 定义每个动作的帧数/循环/帧率，`mood_map` 把情绪
  映射到动作。缺失或损坏会自动回退到**程序化矢量立绘**，保证能跑。

---

## ⚙️ 配置要点（config.json）

| 配置项 | 说明 | 默认 |
|--------|------|------|
| `model.backend` | `auto`/`ollama`/`transformers`/`template` | `auto` |
| `model.path` | 本地 Qwen 权重目录 | `models/Qwen3.5-0.8B` |
| `model.ollama.model` | Ollama 模型标签 | 安装时写入 |
| `ui.sprite.mode` | `image`/`vector`/`auto` | `auto` |
| `ui.sprite.pack` | 立绘包名 | `default` |
| `ui.pet_size` / `theme` | 立绘大小 / 配色(`pink`/`blue`) | `140` / `pink` |
| `behavior.autonomy_*_interval_s` | 自发闲聊间隔范围 | `35`–`90` |
| `behavior.idle_lonely_after_s` | 多久没互动会撒娇 | `600` |
| `behavior.quiet_hours` | 安静时段 | `1`–`6` 点 |

---

## 📚 文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) —— 架构、模块、线程模型、扩展指南。
- [docs/USAGE.md](docs/USAGE.md) —— 详细使用、常见问题与排错。

---

## 📁 项目结构

```
Dolores/
├── run.py / dolores/__main__.py   # 入口
├── config.json                    # 配置
├── windows/                       # Windows 一键安装
│   ├── install.bat / install.ps1  #   安装器
│   ├── run_dolores.bat            #   启动器
│   └── uninstall.ps1
├── assets/
│   ├── sprites/default/           # 内置图片立绘包
│   └── dolores.ico                # 快捷方式图标
├── dolores/
│   ├── app.py                     # 编排（线程/心跳/调度）
│   ├── sensors.py                 # 跨平台系统感知（/proc | Win32 ctypes）
│   ├── personality.py             # 情绪状态机 + 事件
│   ├── autonomy.py                # 自主行为引擎
│   ├── brain/                     # 可插拔大脑
│   │   ├── prompts.py / postprocess.py
│   │   ├── template_brain.py / transformers_brain.py / ollama_brain.py
│   │   └── factory.py             #   多后端回退链
│   └── ui/                        # tkinter + Pillow 界面
│       ├── text_renderer.py / sprite.py / sprite_loader.py
│       └── pet_window.py / bubble.py / chat_input.py
└── scripts/
    ├── generate_sprites.py        # 生成立绘包
    └── gui_smoketest.py           # GUI 自检
```

---

愿 Dolores 陪你度过每一个敲代码的日子 (・ω・)b
