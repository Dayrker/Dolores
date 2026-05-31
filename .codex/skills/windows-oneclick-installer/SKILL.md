---
name: windows-oneclick-installer
description: Build a double-click Windows installer (BAT + PowerShell) for a Python app that auto-installs Python via winget, creates a venv, installs deps, sets up an LLM backend, copies models out of WSL, and creates a desktop shortcut. Use when shipping a Python/WSL-developed app to native Windows users who have no Python, or when a project must "just work" from one double-click.
keywords: [Windows installer, one-click, PowerShell, winget, venv, pythonw, desktop shortcut, WScript.Shell, WSL model copy, wsl.localhost, UTF-8 BOM, PS 5.1, execution policy, torch cu128, Ollama, Store stub python]
---

# Windows one-click installer for a Python app

Ship two files in `windows/`: a tiny `install.bat` (double-clickable) that launches the
real `install.ps1` with the execution policy relaxed.

```bat
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
pause
```

## Hard-won gotchas (each one bit me)

### 1. PowerShell scripts with non-ASCII MUST be saved UTF-8 **with BOM**
Windows PowerShell 5.1 decodes `.ps1` as the ANSI/GBK codepage unless a BOM is present.
Chinese comments → parse errors / garbled tokens. Save as `utf-8-sig`. Verify by parsing
without executing:
```powershell
$e=$null; [void][Management.Automation.Language.Parser]::ParseFile($f,[ref]$null,[ref]$e); $e
```

### 2. The default `python.exe` on Windows is a **Microsoft Store stub**, not Python
`where python` returns `...\WindowsApps\python.exe` which is a fake that opens the Store.
Reject any path containing `WindowsApps`; verify a candidate really works with
`& $exe -c "import venv"`. If none, install real Python:
```powershell
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
# then re-find it (PATH won't refresh in this shell) at:
# $env:LocalAppData\Programs\Python\Python312\python.exe   (py launcher may be absent)
```

### 3. Use a project-local venv + `pythonw.exe` launcher (no console window)
```powershell
& $Python -m venv "$Root\.venv"
$VPy = "$Root\.venv\Scripts\python.exe"; $pyw = "$Root\.venv\Scripts\pythonw.exe"
& $VPy -m pip install --upgrade pip; & $VPy -m pip install Pillow
```
Launcher: `start "" "<.venv>\Scripts\pythonw.exe" "<root>\run.py"`.

### 4. RTX 50-series (Blackwell sm_120) needs torch **cu128**, not cu124
```powershell
& $VPy -m pip install torch --index-url https://download.pytorch.org/whl/cu128
# fall back to CPU wheel on failure
```

### 5. Models living in WSL are **invisible to Windows** (symlink/9P)
A `models/X -> /home/.../cache/...` WSL symlink reads as broken/empty from Windows. To use
it natively, create a **real** directory and copy **dereferenced** files. Easiest: let WSL
push them to the Windows drive (convert `D:\a\b` → `/mnt/d/a/b`):
```powershell
cmd /c "rmdir /s /q `"$ModelDir`" 2>nul"; New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
$drive = $ModelDir.Substring(0,1).ToLower(); $rest = $ModelDir.Substring(2) -replace '\\','/'
wsl -e bash -lc "cp -Lr '$src/.' '/mnt/$drive$rest/'"      # -L dereferences the symlink
# Manual fallback for users: \\wsl.localhost\<distro>\home\...   in Explorer
```

### 6. Desktop shortcut via WScript.Shell COM
```powershell
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\App.lnk")
$sc.TargetPath = $pyw; $sc.Arguments = "`"$Root\run.py`""; $sc.WorkingDirectory = $Root
$sc.IconLocation = "$Root\assets\app.ico"; $sc.Save()
```
Generate the `.ico` from a PNG with Pillow: `img.save("app.ico", sizes=[(16,16),(32,32),(48,48),(256,256)])`.

### 7. Edit config.json by merge, not overwrite
`Config` is usually read-only at runtime; the installer edits JSON directly. Use
`ConvertFrom-Json` / `ConvertTo-Json -Depth 12` to preserve the user's other settings.

### 8. Big downloads (Ollama ~2 GB) over a proxy are slow — don't block
Run `winget`/`ollama pull` **detached** (`Start-Process -RedirectStandardOutput`) and
poll, rather than a single long synchronous call that times out. Always make the app
degrade gracefully if the backend isn't ready yet (see `pluggable-local-llm-backend`).

## Recommended step order

locate root → find/install Python → create venv → pip deps → backend setup (Ollama
install+serve+pull, or torch+model-copy) → generate assets if missing → merge-write config
→ launcher + shortcut → import smoke test (`& $VPy -c "import yourpkg"`).

## Proxy reality (WSL dev box)

A proxy set in `~/.bashrc` often works from **Windows** but is unreachable from **WSL**
(different network namespace). Do all network installs on the Windows side.

> Reference: `windows/install.ps1`, `windows/install.bat`, `windows/run_dolores.bat`,
> `windows/uninstall.ps1`; verified end-to-end (Python 3.12 + venv + Pillow + Ollama +
> qwen3:0.6b) on native Windows. Diagnostics: `scripts/win_selfcheck.py`,
> `scripts/win_ollama_check.py`.
