# Dolores 架构文档

本文记录 Dolores 的整体设计、关键技术取舍与扩展方式。

## 1. 设计目标

1. **能自主反应**：根据电脑状态自发做出表情/对话，不需要用户一直下指令。
2. **萌**：视觉（图片立绘多动作）与话术都走可爱风。
3. **稳**：任何子系统（模型、显示、传感）失效都要优雅降级，绝不整体崩溃。
4. **本地优先 + 跨平台**：本地 LLM（Ollama / Qwen3.5）；原生 Windows 与 Linux/WSL 皆可。

## 2. 运行环境与关键取舍

| 主题 | 现实 | 应对 |
|------|------|------|
| GUI 库 | 不便额外装 PySide/PyQt | 用标准库 **tkinter** |
| 中文/emoji 显示 | WSL 的 conda Tk 无 Xft（只有 'fixed'） | 用 **Pillow 渲染文字成图片**，按平台找字体 |
| 系统指标 | 不想依赖 psutil | Linux 读 `/proc`；Windows 用 **ctypes** 调 Win32 |
| 透明窗口 | X11 下 Tk 无 `-transparentcolor` | `-alpha` 整窗半透明 + 圆角卡片（Windows 原生可后续增强） |
| 模型架构 | Qwen3.5 是 `qwen3_5` | 需 transformers≥5.x；用 `dtype=` + `.to(cuda)`（**不用 device_map**，免 accelerate） |
| RTX 50 系 | Blackwell sm_120 | Windows torch 需 **cu128** 轮子（cu124 不兼容） |
| Windows 无真 Python | 仅应用商店占位 | 安装器用 **winget** 装 Python 3.12 |
| 本地模型在 WSL | 是 WSL 内符号链接，Windows 不可读 | 安装器从 WSL **解引用复制**到真实目录 |

## 3. 模块分层

```
                       ┌──────────── app.py ────────────┐
                       │  编排/线程/心跳/调度/历史        │
                       └──┬───────┬────────┬─────────┬──┘
                   ┌──────▼──┐ ┌──▼─────┐ ┌▼───────┐ ┌▼────────┐
                   │ sensors │ │persona-│ │autonomy│ │   ui/   │
                   │跨平台   │ │ lity   │ │何时开口│ │tk+Pillow│
                   └─────────┘ └────────┘ └────────┘ └────┬────┘
                                                ┌─────────▼─────────┐
                                                │      brain/        │
                                                │ Hybrid 回退链：     │
                                                │ ollama→qwen→模板    │
                                                └────────────────────┘
```

### 3.1 sensors.py —— 跨平台感知
- `BaseSensor` 提供时间/夜间判断；`LinuxSystemSensor`（/proc）、`WindowsSystemSensor`
  （ctypes：`GetSystemTimes` 差分算 CPU%、`GlobalMemoryStatusEx` 取内存）、`NullSensor`（兜底）。
- `create_sensor()` 按 `os.name`/`/proc` 选实现。产出统一的 `SystemState`。

### 3.2 personality.py —— 情绪与事件
- `derive_mood()` 把系统状态映射成情绪；`detect_events()` 检测 CPU/内存高、夜深、寂寞等
  事件，带**去抖 + 冷却**，避免话痨；高危事件压制同类次级告警。

### 3.3 autonomy.py —— 自主行为
- `AutonomyEngine.tick()` 每心跳决策一次：**问候 > 紧急事件 > 定时随机闲聊**；
  安静时段降低主动闲聊概率。只决定“要不要说/说哪类”，不生成文字。

### 3.4 brain/ —— 可插拔大脑（本地优先）
- `base.Brain`：统一接口 `generate(BrainRequest)->BrainReply`。
- `prompts.py`：人设系统提示 + 按触发类型构造消息（各后端共用）。
- `postprocess.py`：清洗思维链/前缀、**去 emoji**、截成一两句（各后端共用）。
- `template_brain.py`：纯标准库可爱话术，永远在线。
- `transformers_brain.py`：本地 HF 模型。transformers 5.x 用 `dtype=` 加载、`.to('cuda')`
  运行；对旧版做参数名回退；失败记 `load_error`、`ready=False`。
- `ollama_brain.py`：纯标准库 urllib 调 `http://127.0.0.1:11434`；`warmup()` 探测服务与模型；
  生成失败抛异常交由回退链。
- `factory.HybridBrain`：持**有序后端列表**，逐个尝试就绪后端，全部失败回退模板；
  `status` 报告当前后端。`create_brain(cfg)` 按 `model.backend`(auto/ollama/transformers/template)
  组装后端顺序与构造参数（此处不加载权重，交 `warmup`）。

### 3.5 ui/ —— 界面（tkinter + Pillow）
- `text_renderer.py`：按平台发现字体（Windows `%SystemRoot%\Fonts`；Linux/WSL `/mnt/c`+
  `~/.local/share/fonts`+常见路径），`render_text()` 渲染文字成 RGBA 图，`sanitize()` 剔除
  无字形字符（防豆腐块 + 防 LLM 乱码）。
- `sprite.py`：程序化矢量小精灵（保底） + **Animator/make_animator**：统一图片包与矢量两种
  来源，按动作 fps 推进，支持情绪驱动循环动作 + `trigger()` 一次性动作播完回 idle。
- `sprite_loader.py`：从 `assets/sprites/<pack>/` 按 `manifest.json` 加载帧序列与
  mood→action 映射；缺失/损坏返回 None → 回退矢量。
- `pet_window.py`：无边框置顶可拖拽主窗，Canvas 显示 Animator 帧；单击=戳（bounce）、
  双击=聊天、右键菜单。`bubble.py` 圆角气泡，`chat_input.py` 隐藏 Entry 捕获中文 + Pillow 预览。

## 4. 线程模型

- **主线程**：tkinter `mainloop` + 全部 UI；`root.after()` 跑心跳。
- **BrainWorker（后台线程）**：从 `in_q` 取任务→`brain.generate()`→`out_q`；启动时先
  `brain.warmup()` 后台加载（Ollama 探测 / 模型权重），不阻塞 UI。
- **心跳**（每 `sensor_interval_ms`）：采样→更新情绪/立绘→（空闲时）自主决策投任务→
  取回结果切表情/弹气泡。用序号 `seq` 只接受最新在途结果；用户输入 `force` 抢占。
- 身体语言：问候→`wave`、戳/兴奋→`bounce`（在主线程触发 Animator）。

## 5. Windows 一键安装（windows/install.ps1）

步骤：定位项目根 → 找/winget 装真 Python（排除应用商店占位）→ 建 `.venv` →
装 Pillow（+按后端装 torch cu128/transformers）→ 后端准备（ollama: winget 装 + serve +
pull + 写回 config / transformers: 从 WSL 解引用复制 1.7GB 模型到真实目录）→ 生成立绘 →
安全合并写 `config.json` → 生成启动器 `run_dolores.bat` + 桌面快捷方式 → 导入自检。
脚本以 **UTF-8 BOM** 保存以兼容 Windows PowerShell 5.1 的中文解析。

## 6. 错误与降级

配置坏→默认值；`/proc` 不可读或平台未知→`NullSensor`(available=False)；
后端不可用→沿回退链直到模板；单次生成异常→下一后端/模板；字体缺字形→`sanitize` 剔除；
立绘包缺失→矢量立绘；`-alpha` 不支持→`try/except` 跳过。

## 7. 扩展指南

- **换立绘**：放一套 PNG 到 `assets/sprites/<pack>/` + manifest，改 `ui.sprite.pack`；
  或改 `scripts/generate_sprites.py` 重生成。
- **加情绪/动作**：`personality.MOODS`/`detect_events` + manifest `mood_map`/`actions` +
  （矢量）`sprite.py` 表情分支 / 生成器动作函数。
- **接新推理后端**：实现 `Brain` 子类（仿 `ollama_brain.py`），在 `factory.create_brain` 装配。
- **加感知维度**（电量/网络/窗口标题…）：扩展 `SystemState` 与各平台 sensor，再在
  `personality` 映射成情绪/事件。

## 8. 自检

```bash
# 纯逻辑：python -c "import dolores.app"
# 各后端选择：改 config model.backend 后运行 create_brain().warmup() 看 status
# GUI 冒烟：python scripts/gui_smoketest.py
# 原生 Windows：.venv\Scripts\python.exe scripts\win_selfcheck.py
```
