# Dolores 架构文档

本文记录 Dolores 的整体设计、关键技术取舍与扩展方式。

## 1. 设计目标

1. **能自主反应**：根据电脑状态自发做出表情/对话，不需要用户一直下指令。
2. **萌**：视觉与话术都走可爱风。
3. **稳**：任何子系统（模型、显示、传感）失效都要优雅降级，绝不整体崩溃。
4. **本地优先**：尽量用本地 Qwen 模型；用不了时也要能跑。

## 2. 运行环境与硬约束

| 约束 | 现实 | 应对 |
|------|------|------|
| 不能联网 | pip 走代理失败 | 只用环境已有的包：标准库 + torch/transformers + Pillow |
| 不能装 GUI 库 | 无 PySide6/PyQt | 用标准库 **tkinter** |
| conda Tk 无 Xft | `font families` 仅 `fixed`，**无法显示中文/emoji** | 用 **Pillow 把文字渲染成图片**再贴到 Tk |
| 无 `-transparentcolor` | X11 下 Tk 不支持按色键透明 | 用 `-alpha` 整窗半透明 + 圆角卡片观感 |
| 无 psutil | 缺包 | 直接读 `/proc/stat`、`/proc/meminfo` + `os.getloadavg()` |
| 模型架构太新 | `qwen3_5` 不被 transformers 4.56.1 识别 | 大脑做**可插拔 + 自动回退**；升级 transformers 即自动启用 |

> 字体：WSL 下可直接读取 Windows 侧 `/mnt/c/Windows/Fonts/`（微软雅黑 `msyh.ttc`、
> 黑体 `simhei.ttf`、Segoe UI Emoji `seguiemj.ttf`），Pillow 用绝对路径加载它们。

## 3. 模块分层

```
            ┌──────────────────────────────────────────┐
            │                  app.py                    │
            │  编排 / 线程 / 心跳 / 调度 / 历史           │
            └───┬───────────┬───────────┬───────────┬───┘
                │           │           │           │
          ┌─────▼────┐ ┌────▼─────┐ ┌───▼────┐ ┌────▼─────┐
          │ sensors  │ │personality│ │autonomy│ │   ui/    │
          │ (/proc)  │ │情绪+事件  │ │何时开口│ │ tkinter  │
          └──────────┘ └──────────┘ └────────┘ └──────────┘
                                          │
                                    ┌─────▼──────┐
                                    │   brain/   │
                                    │ Hybrid:    │
                                    │ LLM→模板   │
                                    └────────────┘
```

### 3.1 sensors.py —— 感知
- `SystemSensor.read()` 返回 `SystemState` 快照（CPU% / 内存% / 负载 / 时间 / 是否夜间）。
- CPU% 用两次 `/proc/stat` 差分；对象保存上次累计值，构造时预热一次。
- 非 Linux 平台 `/proc` 不存在 → 返回 `available=False`，上层照常运行。

### 3.2 personality.py —— 情绪与事件
- `MOODS`：情绪集合（happy/comfy/excited/curious/worried/panic/sleepy/lonely）。
- `Personality.derive_mood(sys, pet)`：把系统状态映射成当前情绪。
- `Personality.detect_events(sys, pet)`：检测值得反应的**事件**（CPU 爆表、夜深、寂寞…），
  带**去抖**（连续多次采样才报警）和**冷却**（同类事件一段时间内不重复），避免话痨。
- `PetState`：Dolores 的内在状态（情绪、精力、上次互动时间）。

### 3.3 autonomy.py —— 自主行为
- `AutonomyEngine.tick(sys, pet)` 每个心跳调用，返回一个 `Intent`（说话意图）或 `None`。
- 优先级：**开场问候 > 紧急事件 > 定时随机闲聊**。
- 安静时段（夜间）会大幅降低主动闲聊概率，但紧急事件仍会触发。
- 注意：它只决定「要不要说、说哪一类」，**不生成具体文字**——那是大脑的职责。

### 3.4 brain/ —— 可插拔大脑
- `base.Brain`：统一接口，`generate(BrainRequest) -> BrainReply`。
- `TemplateBrain`：纯标准库。分门别类的萌系语料 + 关键词匹配 + 去重 + 颜文字点缀。
  **永远可用**，是保底人格。
- `TransformersBrain`：封装本地 HuggingFace 因果模型。
  - `warmup()` 真正加载权重（在后台线程调用）；失败时记录 `load_error`、`ready=False`。
  - 系统提示词把人设、简短风格、纯中文等规则注入。
  - 输出做后处理：剥离 `<think>` 思维链、去角色名前缀、截断到一两句。
- `factory.HybridBrain`：组合二者。`generate` 时若 LLM 就绪则用之，**任何异常/空输出回退模板**。
  `status` 属性对外汇报当前用的是哪种大脑。
- `factory.create_brain(cfg)`：按配置装配（此时**不加载权重**，交给 warmup）。

### 3.5 ui/ —— 界面（tkinter + Pillow）
- `text_renderer.py`：核心适配层。`render_text()` 用 Pillow + TTF 把文字画成 RGBA 图；
  `sanitize()` 剔除字体里没有字形的字符（豆腐块预防，尤其防 LLM 乱码）。
- `sprite.py`：程序化绘制小精灵。按情绪画眼睛/嘴巴/眉毛，带腮红、高光、呆毛；
  `render_frame()` 加上下浮动动画。结果用 `lru_cache` 缓存。
- `pet_window.py`：无边框、置顶、可拖拽主窗；Canvas 显示立绘；承载气泡与输入框；
  绑定单击（戳）/双击（聊天）/右键菜单。
- `bubble.py`：圆角对话卡片（带指向立绘的小尾巴），超时自动隐藏，自动夹在屏幕内。
- `chat_input.py`：手动输入。隐藏的 `Entry` 捕获按键（Tk 能正确**存储**中文，只是不能显示），
  再用 Pillow 实时渲染输入预览。

## 4. 线程模型（关键）

tkinter 要求所有 UI 操作在主线程；而 LLM 推理可能很慢。因此：

- **主线程**：tkinter `mainloop` + 全部 UI；用 `root.after(interval)` 跑**心跳**。
- **BrainWorker（后台线程）**：循环从 `in_q` 取任务、`brain.generate()`、把结果放 `out_q`。
  启动时先 `brain.warmup()` 后台加载模型，**不阻塞 UI 启动**。
- **心跳流程**（每 `sensor_interval_ms`）：
  1. `sensor.read()` 采样 → 更新情绪立绘；
  2. 若无在途请求，`autonomy.tick()` 产生意图 → 投 `in_q`；
  3. `_drain_results()` 取回结果 → 切表情 + 弹气泡 + 记历史。
- 用**序号 `seq`** 标记在途请求，只接受最新一次的结果，避免叠加与错位。
- 用户主动输入用 `force=True` 抢占，保证响应。

## 5. 错误与降级策略

- 配置坏掉 → 用内置默认值。
- `/proc` 不可读 → `available=False`，照常运行。
- 模型加载失败 → 回退模板大脑（最常见路径，**预期行为**）。
- 单次生成异常 → 回退模板，并给一句兜底话。
- 字体缺字形 → `sanitize()` 剔除，不显示豆腐块。
- `-alpha` 不被支持 → `try/except` 跳过，窗口照常显示。

## 6. 扩展指南

- **换立绘风格**：改 `ui/sprite.py` 的 `THEMES` 与绘制函数，或加新主题键。
- **加新情绪/事件**：在 `personality.py` 的 `MOODS`/`detect_events` 增加，并在
  `template_brain.LINES` 补充对应语料；`sprite.py` 加该情绪的表情分支。
- **接别的模型**：实现一个新的 `Brain` 子类（如 `OllamaBrain`），在 `factory.create_brain` 里装配。
- **加感知维度**（电量、网络、窗口标题…）：在 `sensors.py` 扩展 `SystemState` 与读取逻辑，
  再在 `personality` 里映射成情绪/事件。

## 7. 自检

```bash
# 纯逻辑（无 GUI）：导入 + 感知→情绪→自主→模板大脑链路
/home/dayrker/anaconda3/envs/torch2.10/bin/python -c "import dolores.app"

# GUI 冒烟（启动→演示→自动退出）
/home/dayrker/anaconda3/envs/torch2.10/bin/python scripts/gui_smoketest.py
```
