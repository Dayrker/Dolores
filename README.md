# 🌸 Dolores · 桌面萌宠小精灵

> 一只住在你电脑里、会观察电脑状态、像有一点点自主意识的萌系桌面宠物。

Dolores（朵拉）会安静地待在屏幕角落，用可爱的小表情陪着你。她能感知 CPU /
内存 / 时间等电脑状态，并**自发**地做出反应——CPU 飙高会惊慌、夜深了会提醒你
休息、太久没理她会撒娇。你不用一直给她下指令，但随时可以双击她、打字和她聊天。

后端大脑设计成**可插拔**：默认用一套零依赖的「模板大脑」即可生动地说话；当本地
大模型可用时（见下文），会自动切换到本地 LLM 生成更自然的对话。

```
        ╭──────────────────────────────╮
        │ 你好呀主人～朵拉上线啦！        │
        │ 今天 CPU 好凉快哦 (≧▽≦)        │
        ╰───────────────╮──────────────╯
                         ╲    ╭───────╮
                              │ (・ω・) │   ← 会浮动、会换表情、可拖拽
                              ╰───────╯
```

---

## ✨ 特性

- **实时感知电脑状态**：CPU、内存、系统负载、时间段（纯读 `/proc`，不依赖 psutil）。
- **情绪 + 自主行为**：内置情绪状态机（开心 / 悠闲 / 兴奋 / 担心 / 惊慌 / 困倦 / 寂寞），
  由系统状态驱动；自主引擎决定**何时自己开口**，无需手动指令。
- **萌系立绘**：用 Pillow 程序化绘制的小精灵，会上下浮动、按情绪切换表情（无需任何美术素材）。
- **对话气泡 + 手动聊天**：双击或右键即可打字和她聊天，支持中文输入。
- **可插拔大脑**：
  - `TemplateBrain`：零依赖、永远在线的可爱话术引擎（默认）。
  - `TransformersBrain`：尝试加载本地 Qwen 模型；失败则自动回退模板大脑。
- **稳定优先**：模型加载在后台线程，UI 秒开；任何一环出错都优雅降级，不崩溃。

---

## 🚀 快速开始

> 本项目固定使用指定的 conda 环境解释器：
> `/home/dayrker/anaconda3/envs/torch2.10/bin/python`

```bash
cd /mnt/d/Linux/Dolores

# 直接运行
/home/dayrker/anaconda3/envs/torch2.10/bin/python run.py

# 或者用模块方式
/home/dayrker/anaconda3/envs/torch2.10/bin/python -m dolores
```

启动后，Dolores 会出现在屏幕右下角并和你打招呼。

### 交互方式

| 操作 | 效果 |
|------|------|
| **单击**她 | 戳一戳，她会开心地反应 |
| **双击**她 | 打开聊天输入框 |
| **拖拽** | 把她拖到任意位置 |
| **右键** | 菜单：说话 / 戳一戳 / 退出 |
| 聊天框里 **回车** | 发送消息 |
| 聊天框里 **Esc** | 关闭输入框 |

---

## 🧠 关于本地大模型（重要）

`models/Qwen3.5-0.8B` 是 **Qwen3.5** 系列（架构标识 `qwen3_5`）。
当前环境的 `transformers==4.56.1` **尚不支持**该架构，因此启动时模型会加载失败，
Dolores 会**自动回退到模板大脑**——她依然活泼可爱，只是话术来自内置语料库。

这是**预期行为**，不是 bug。一旦你把 transformers 升级到支持 `qwen3_5` 的版本，
Dolores 会在下次启动时**自动启用本地 LLM**，无需改任何代码：

```bash
# 待有网络时（任选其一）
pip install --upgrade transformers
# 或装最新源码版
pip install git+https://github.com/huggingface/transformers.git
```

升级后日志会显示 `大脑：本地模型大脑 ✨`。
也可以在 `config.json` 里把 `"model.enabled"` 设为 `false` 来始终使用模板大脑。

---

## ⚙️ 配置

所有配置在项目根目录的 [config.json](config.json)，缺失字段会用内置默认值兜底。常用项：

| 配置项 | 说明 | 默认 |
|--------|------|------|
| `character.name` | 角色名 | `Dolores` |
| `model.enabled` | 是否尝试加载本地 LLM | `true` |
| `model.path` | 模型目录（相对项目根） | `models/Qwen3.5-0.8B` |
| `ui.pet_size` | 立绘像素大小 | `140` |
| `ui.start_corner` | 初始角落 | `bottom-right` |
| `ui.theme` | 配色（`pink` / `blue`） | `pink` |
| `behavior.sensor_interval_ms` | 状态采样间隔（毫秒） | `2000` |
| `behavior.autonomy_min_interval_s` / `max` | 自发闲聊的随机间隔范围（秒） | `35` / `90` |
| `behavior.idle_lonely_after_s` | 多久没互动会撒娇（秒） | `600` |
| `behavior.thresholds.cpu_high` 等 | 触发反应的阈值 | 见文件 |
| `behavior.quiet_hours` | 安静时段（减少打扰） | `1`–`6` 点 |

---

## 📚 文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) —— 架构与各模块设计、线程模型、扩展指南。
- [docs/USAGE.md](docs/USAGE.md) —— 详细使用、常见问题与排错。

---

## 🛠️ 技术栈与环境约束

- **Python 3.10**（conda 环境 `torch2.10`）
- **GUI：标准库 tkinter** —— 因当前环境无法联网安装 PySide6/PyQt。
- **文字渲染：Pillow** —— 该环境的 conda Tk 未链接 Xft，无法直接显示中文/颜文字，
  故所有文字（立绘表情、气泡、输入预览）都用 Pillow 按 TTF 渲染成图片再贴到界面。
  中文/emoji 字体直接读取 Windows 侧的 `msyh.ttc` / `seguiemj.ttf`（WSL 环境）。
- **系统指标：`/proc`** —— 不依赖 psutil。
- **可选：torch + transformers** —— 本地 LLM 后端（见上文）。

> 这些取舍都源于「离线 + 该环境 Tk 受限」的现实，详见架构文档。

---

## 📁 项目结构

```
Dolores/
├── run.py                  # 启动入口
├── config.json             # 配置
├── requirements.txt        # 依赖说明（环境已具备）
├── dolores/
│   ├── app.py              # 应用编排（线程/心跳/调度）
│   ├── config.py           # 配置加载
│   ├── sensors.py          # /proc 系统状态感知
│   ├── personality.py      # 情绪状态机 + 事件检测
│   ├── autonomy.py         # 自主行为引擎（何时开口）
│   ├── brain/              # 可插拔大脑
│   │   ├── base.py         #   接口与数据类
│   │   ├── template_brain.py  # 零依赖话术引擎
│   │   ├── transformers_brain.py # 本地 LLM 后端
│   │   └── factory.py      #   Hybrid 回退逻辑
│   └── ui/                 # tkinter + Pillow 界面
│       ├── text_renderer.py   # 文字→图片（绕开 Tk 字体限制）
│       ├── sprite.py          # 程序化萌系立绘
│       ├── pet_window.py      # 主角窗口
│       ├── bubble.py          # 对话气泡
│       └── chat_input.py      # 手动输入框
├── scripts/
│   └── gui_smoketest.py    # GUI 自检脚本
└── docs/
    ├── ARCHITECTURE.md
    └── USAGE.md
```

---

## 📝 许可

个人项目，自由使用。模型权重版权归 Qwen 团队所有（见 `models/.../LICENSE`）。

愿 Dolores 陪你度过每一个敲代码的日子 (・ω・)b
