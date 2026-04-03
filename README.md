# Dolores

一个名为 **Dolores** 的 AI 多模态人工意识项目起点。

当前阶段目标：
1. 先完成稳定的文本对话闭环。
2. 默认尝试 `Gemma 4 26B A4B`。
3. 如果显存/吞吐不足，自动降级到 `Gemma 4 E4B`。

> 项目后续可在此基础上扩展语音、图像、传感器等多模态输入输出。

---

## 第一步：本地文本对话（Ollama）

`dolores_chat.py` 提供了一个最小可用的对话 CLI：
- 优先模型：`gemma4:26b-a4b`
- 兜底模型：`gemma4:e4b`
- 自动检测本地已安装模型
- 支持自动拉取兜底模型（可选）

### 1) 环境准备

- 安装 Python 3.10+
- 安装并启动 Ollama（默认 API: `http://127.0.0.1:11434`）

### 2) 运行

```bash
python3 dolores_chat.py
```

可选参数：

```bash
python3 dolores_chat.py \
  --endpoint http://127.0.0.1:11434 \
  --primary gemma4:26b-a4b \
  --fallback gemma4:e4b \
  --auto-pull
```

### 3) 交互

- 输入问题后回车即可获取回复。
- 输入 `/model` 查看当前使用模型。
- 输入 `/switch` 手动切换到兜底模型。
- 输入 `/quit` 结束会话。

---

## 5090 单卡建议

- 先尝试 `gemma4:26b-a4b`；如果响应慢或 OOM，切到 `gemma4:e4b`。
- 将 `num_ctx`、`temperature`、`top_p` 调小可进一步降低负载。
- 多模态能力建议分阶段引入：
  1. 文本理解与记忆
  2. 语音输入（ASR）与语音输出（TTS）
  3. 图像理解（VLM）
  4. 自动反馈策略（规则 + Agent 调度）
