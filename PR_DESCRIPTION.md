# fix(windows): 修复双击 install.bat 在中文 Windows 上的乱码报错

## 背景

之前的 MR 合入后,在中文版 Windows 上**双击 `install.bat` 直接报错**:

```
'敤瀹冦€?setlocal' 不是内部或外部命令,也不是可运行的程序...
'涓€閿畨瑁?echo' 不是内部或外部命令...
请按任意键继续... (按键后直接退出,什么也没发生)
```

## 原因

**`.bat` 文件编码问题**:中文版 Windows 的 cmd 按 GBK(OEM 代码页)读取批处理文件,
但文件存成了 UTF-8。里面的中文注释/`echo` 被解码成乱码,然后被 cmd 当成命令执行 →
一连串"不是内部或外部命令"。

> 注意这跟 `.ps1` 正好相反:`.ps1` 需要 UTF-8 **BOM**,`.bat` 则需要**纯 ASCII**。
> 两种文件的编码规则相反,很容易顾此失彼。

## 改动

- **`install.bat` / `run_dolores.bat`**:改为**纯 ASCII(英文)+ CRLF** 换行。
- **`install.ps1` / `uninstall.ps1`**:控制台输出与注释改为英文(纯 ASCII,不再依赖
  UTF-8 BOM),**功能完全不变**。
- **`.codex` Skill 文档**:把这个坑补进 `windows-oneclick-installer`,新增 `.ps1` vs
  `.bat` 编码规则对照表,并给出最稳策略——脚本只输出英文,本地化文字放进 Python 应用
  (用 Pillow 渲染),让编码问题彻底咬不到。

涉及文件(6 个,+125 / -112):
```
windows/install.bat        | 纯 ASCII + CRLF
windows/run_dolores.bat    | 纯 ASCII + CRLF
windows/install.ps1        | 英文输出(纯 ASCII)
windows/uninstall.ps1      | 英文输出(纯 ASCII)
.codex/skills/windows-oneclick-installer/SKILL.md  | 新增 BAT 编码坑 + 对照表
.codex/README.md           | 核心教训速查同步补充
```

## 验证

**已在原生 Windows 双击实测**:输出全为干净英文、无乱码、无"不是内部或外部命令"报错,
且安装全流程跑通:
`Python → venv → Pillow → Ollama → pull qwen3:0.6b → 写 config → 立绘 → 导入自检 import-ok → 完成`。

## 提交

- `f98c1d5` fix(windows): ASCII+CRLF bat & English ps1 output (fix mojibake on cmd)
- `f3bb823` docs(.codex): add BAT-encoding gotcha to windows-installer skill

🤖 Generated with [Claude Code](https://claude.com/claude-code)
