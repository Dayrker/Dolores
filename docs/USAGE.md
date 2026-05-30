# Dolores 使用指南

## 启动

```bash
cd /mnt/d/Linux/Dolores
/home/dayrker/anaconda3/envs/torch2.10/bin/python run.py
```

> 必须用上面这个解释器（conda 环境 `torch2.10`），它带齐了 torch / transformers / Pillow。
> 用系统 python 可能缺 Pillow 或 Tk 而无法启动。

启动后，朵拉出现在屏幕右下角并和你打招呼。关闭：右键 → 退出，或在终端按 `Ctrl+C`。

## 和她互动

| 操作 | 效果 |
|------|------|
| 单击 | 戳一戳，她会开心反应 |
| 双击 | 打开聊天输入框 |
| 拖拽 | 移动她的位置 |
| 右键 | 菜单：对朵拉说话 / 戳一戳 / 退出 |
| 输入框回车 | 发送 |
| 输入框 Esc | 关闭输入框 |

她也会**自己**说话：定时随机闲聊、CPU/内存飙高时惊呼、夜深提醒休息、太久没理她会撒娇。

## 她会对什么作出反应？

- **CPU 高 / 极高**：担心 / 惊慌（阈值见 `config.json` 的 `behavior.thresholds`）。
- **内存 高 / 极高**：提醒你关点东西。
- **夜深**（默认 1–6 点）：困倦，劝你早睡。
- **久未互动**（默认 10 分钟）：寂寞，求关注。
- **空闲清爽**：悠闲发呆、卖萌。

## 让她更聪明（启用本地大模型）

默认她用「模板大脑」（内置语料），因为当前 `transformers` 版本还不认识
`models/Qwen3.5-0.8B` 的 `qwen3_5` 架构。等你能联网时升级即可自动启用本地 LLM：

```bash
pip install --upgrade transformers
# 或
pip install git+https://github.com/huggingface/transformers.git
```

升级后重新启动，终端日志出现 `大脑：本地模型大脑 ✨` 即表示已用上本地模型。

不想用模型、只用模板大脑：把 `config.json` 里 `model.enabled` 改为 `false`。

## 常见问题

**Q：界面文字是方块 □？**
A：理论上不会——文字都经 Pillow 渲染。若出现，多半是没找到中文字体。确认
`/mnt/c/Windows/Fonts/msyh.ttc` 存在；或把任意中文 TTF 放到
`~/.local/share/fonts/` 后重试。可在 `dolores/ui/text_renderer.py` 的
`_CJK_CANDIDATES` 里补充字体路径。

**Q：窗口有个浅色方框，不是纯透明？**
A：当前环境的 Tk 在 X11 下不支持按色键透明（`-transparentcolor`），只能整窗
`-alpha` 半透明。这是平台限制，已尽量用接近背景的浅色弱化方框感。

**Q：启动报错找不到 `dolores`？**
A：请在项目根目录 `/mnt/d/Linux/Dolores` 下运行，或用 `python -m dolores`。

**Q：完全没有窗口出现？**
A：确认 `echo $DISPLAY` 有值（WSLg 下通常是 `:0`）。在纯无显示环境无法显示 GUI。

**Q：CPU% 一开始显示 0？**
A：正常。CPU% 需要两次采样差分，启动后一两个心跳就准确了。

**Q：她太吵 / 太安静？**
A：调 `config.json` 的 `behavior.autonomy_min_interval_s` 与 `autonomy_max_interval_s`
（自发闲聊的随机间隔范围），以及 `quiet_hours`（安静时段）。

**Q：模型加载日志报 `qwen3_5` not recognized？**
A：这是**预期**的回退提示，不影响使用。见上文「启用本地大模型」。

## 自检脚本

```bash
# GUI 冒烟：启动→演示问候/惊慌/输入框→自动退出
/home/dayrker/anaconda3/envs/torch2.10/bin/python scripts/gui_smoketest.py
```

终端打印 `app exited cleanly` 表示全链路正常。
