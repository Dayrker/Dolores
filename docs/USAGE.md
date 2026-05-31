# Dolores 使用指南

## 安装与启动

### Windows（推荐，一键）
1. 把项目放在 Windows 可访问处（如 `D:\Linux\Dolores`）。
2. 进入 `windows\`，双击 **`install.bat`**，按提示等待完成。
3. 双击桌面「**Dolores**」启动。也可运行 `windows\run_dolores.bat`。

默认用 **Ollama** 后端（安装时自动装好并拉取小模型）。
想用本地 Qwen3.5 权重 + GPU：
```powershell
powershell -ExecutionPolicy Bypass -File windows\install.ps1 -Backend transformers
```

### Linux / WSL
```bash
cd /mnt/d/Linux/Dolores
python -m dolores         # 或 python run.py
```
需要 Pillow（必需）；若用本地 Qwen 后端，还需 torch + transformers(≥5.x)。

关闭：右键 → 退出，或终端 `Ctrl+C`。

## 和她互动

| 操作 | 效果 |
|------|------|
| 单击 | 戳一戳，她蹦跶一下 |
| 双击 | 打开聊天输入框 |
| 拖拽 | 移动位置 |
| 右键 | 菜单：说话 / 戳一戳 / 退出 |
| 输入框回车 / Esc | 发送 / 关闭 |

她也会**自己**说话：定时闲聊、CPU/内存高时惊呼、夜深提醒、久未互动撒娇，并配合
挥手/蹦跶/打瞌睡等动作。

## 选择大脑后端

编辑 `config.json` 的 `model.backend`：
- `auto`（默认）：Ollama → 本地 Qwen → 模板，自动选可用的。
- `ollama`：只用 Ollama。需 `ollama serve` 在跑且已 `ollama pull <模型>`；模型名填 `model.ollama.model`。
- `transformers`：只用本地权重 `models/Qwen3.5-0.8B`（需 transformers≥5.x + torch）。
- `template`：只用内置话术，不加载模型。

启动日志会打印 `大脑：…`，可据此判断当前用的是哪种后端。

## 自定义立绘

1. 仿照 `assets/sprites/default/` 准备一套 PNG（`<动作>_<帧号>.png`）+ `manifest.json`。
2. `config.json` 里设 `ui.sprite.pack` 为你的包名，`ui.sprite.mode` 设 `image` 或 `auto`。
3. 重启即可。想重生成内置包：`python scripts/generate_sprites.py`。

`manifest.json` 关键字段：`actions`（每动作 frames/loop/fps）、`mood_map`（情绪→动作）、
`anchor`（对齐，默认 bottom-center）。

## 常见问题

**Q：界面文字是方块 □？**
A：文字都经 Pillow 渲染。若出现，多半没找到中文字体。Windows 确认
`C:\Windows\Fonts\msyh.ttc` 存在；Linux 可把中文 TTF 放 `~/.local/share/fonts/`，
或在 `dolores/ui/text_renderer.py` 的候选里补路径。

**Q：Ollama 后端不生效？**
A：确认 `ollama serve` 在运行（`http://127.0.0.1:11434` 可访问），且
`ollama list` 里有 `model.ollama.model` 指定的模型。否则会回退模板大脑。

**Q：本地 Qwen(transformers) 后端报错？**
A：需要 `transformers≥5.x`（支持 `qwen3_5`）与可用的 torch。Windows + RTX 50 系
要装 cu128 版 torch（一键安装的 `-Backend transformers` 会处理）。失败会回退模板。

**Q：Windows 一键安装卡在 Ollama？**
A：Ollama 安装包较大，首次下载较慢，请耐心等待；模型拉取同理。即使失败，Dolores
仍会以模板大脑正常运行，之后可手动 `ollama pull` 再重启。

**Q：窗口有浅色方框？**
A：X11 下 Tk 不支持按色键透明，只能整窗 `-alpha`。原生 Windows 观感更好。

**Q：CPU% 一开始是 0？**
A：正常，CPU% 需两次采样差分，一两个心跳后即准确。

**Q：她太吵/太安静？**
A：调 `behavior.autonomy_min_interval_s`/`autonomy_max_interval_s` 与 `quiet_hours`。

## 自检脚本

```bash
# GUI 冒烟（启动→演示→自动退出）
python scripts/gui_smoketest.py
# 原生 Windows 自检（venv 内运行）
.venv\Scripts\python.exe scripts\win_selfcheck.py
```
