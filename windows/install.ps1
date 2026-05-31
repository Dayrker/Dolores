<#
  Dolores 桌面萌宠 - Windows 一键安装脚本
  做的事：
    1. 找/装 真正的 Python（缺失则用 winget 安装 Python 3.12）
    2. 在项目下创建虚拟环境 .venv 并装依赖（Pillow 必装）
    3. 按所选后端准备：
         - ollama（默认）：装 Ollama + 拉取小模型 + 写回 config
         - transformers：装 torch/transformers + 从 WSL 复制本地 Qwen3.5 模型
    4. 生成立绘（若缺）
    5. 写 config.json（合并，不覆盖用户其它设置）
    6. 创建启动器 run_dolores.bat + 桌面快捷方式
    7. 冒烟自检

  用法（在 windows\ 目录或双击 install.bat）：
    install.ps1 [-Backend ollama|transformers] [-OllamaModel <tag>] [-NoShortcut]
#>
param(
  [ValidateSet("ollama", "transformers")]
  [string]$Backend = "ollama",
  [string]$OllamaModel = "qwen3:0.6b",
  [switch]$NoShortcut
)

$ErrorActionPreference = "Stop"
function Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[X] $m" -ForegroundColor Red; exit 1 }

# ---------- Step 0：定位项目根 ----------
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Info "项目根目录：$Root"
Set-Location $Root

# ---------- Step 1：找/装真正的 Python ----------
function Test-RealPython($exe) {
  if (-not $exe) { return $false }
  if ($exe -like "*WindowsApps*") { return $false }  # 应用商店占位符
  try { & $exe -c "import venv,sys;sys.exit(0)" 2>$null; return ($LASTEXITCODE -eq 0) }
  catch { return $false }
}

function Find-Python {
  $cands = @()
  try { $cands += (Get-Command py -ErrorAction SilentlyContinue).Source } catch {}
  try { $cands += (Get-Command python -ErrorAction SilentlyContinue).Source } catch {}
  $cands += @(
    "$env:LocalAppData\Programs\Python\Python312\python.exe",
    "$env:LocalAppData\Programs\Python\Python311\python.exe",
    "C:\Python312\python.exe", "C:\Python311\python.exe"
  )
  foreach ($c in $cands) { if ($c -and (Test-Path $c) -and (Test-RealPython $c)) { return $c } }
  # py 启动器特殊处理
  $pylauncher = (Get-Command py -ErrorAction SilentlyContinue)
  if ($pylauncher -and ($pylauncher.Source -notlike "*WindowsApps*")) { return "py" }
  return $null
}

$Python = Find-Python
if (-not $Python) {
  Info "未找到可用 Python，正在用 winget 安装 Python 3.12…"
  winget install -e --id Python.Python.3.12 --source winget `
    --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) { Die "Python 安装失败。请手动安装 Python 3.12 后重试。" }
  Start-Sleep -Seconds 3
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path", "User")
  $Python = Find-Python
  if (-not $Python) { Die "安装后仍未找到 Python，请重开终端再运行本脚本。" }
}
Ok "使用 Python：$Python"

# ---------- Step 2：创建虚拟环境 ----------
$VenvDir = Join-Path $Root ".venv"
$VPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VPy)) {
  Info "创建虚拟环境 .venv …"
  if ($Python -eq "py") { & py -3 -m venv $VenvDir } else { & $Python -m venv $VenvDir }
  if (-not (Test-Path $VPy)) { Die "虚拟环境创建失败。" }
}
Ok "虚拟环境就绪：$VenvDir"

# ---------- Step 3：安装 Python 依赖 ----------
Info "升级 pip…"
& $VPy -m pip install --upgrade pip --quiet
Info "安装 Pillow（必需）…"
& $VPy -m pip install --quiet Pillow
if ($LASTEXITCODE -ne 0) { Die "Pillow 安装失败（检查网络/代理）。" }

if ($Backend -eq "transformers") {
  # RTX 50 系（Blackwell, sm_120）需要 cu128 轮子；cu124 会报 sm_120 不兼容。
  Info "安装 torch (cu128, 支持 RTX 50 系) + transformers（失败回退 CPU）…"
  & $VPy -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cu128
  if ($LASTEXITCODE -ne 0) {
    Warn "CUDA(cu128) 版 torch 安装失败，改装 CPU 版（生成会慢些）…"
    & $VPy -m pip install --quiet torch
  }
  & $VPy -m pip install --quiet transformers safetensors
  if ($LASTEXITCODE -ne 0) { Die "transformers 安装失败。" }
  Ok "transformers 后端依赖就绪"
}
Ok "Python 依赖安装完成"

# ---------- Step 4：后端准备 ----------
if ($Backend -eq "ollama") {
  Info "准备 Ollama 后端…"
  $ollama = (Get-Command ollama -ErrorAction SilentlyContinue)
  if (-not $ollama) {
    Info "未检测到 Ollama，正在用 winget 安装…"
    winget install -e --id Ollama.Ollama --source winget `
      --accept-package-agreements --accept-source-agreements
    Start-Sleep -Seconds 3
    $env:Path += ";$env:LocalAppData\Programs\Ollama"
  }
  # 启动 ollama 服务（若未运行）
  try {
    Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null
  } catch {
    Info "启动 Ollama 服务…"
    Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
  }
  Info "拉取模型 $OllamaModel（首次较慢）…"
  & ollama pull $OllamaModel
  if ($LASTEXITCODE -ne 0) {
    Warn "拉取 $OllamaModel 失败，尝试备用 qwen2.5:0.5b …"
    $OllamaModel = "qwen2.5:0.5b"
    & ollama pull $OllamaModel
    if ($LASTEXITCODE -ne 0) { Warn "Ollama 模型拉取失败；Dolores 仍会以模板大脑运行。" }
  }
  Ok "Ollama 后端准备完成（模型：$OllamaModel）"
}

if ($Backend -eq "transformers") {
  Info "准备本地 Qwen3.5 模型文件…"
  $ModelDir = Join-Path $Root "models\Qwen3.5-0.8B"
  $haveModel = (Test-Path (Join-Path $ModelDir "config.json"))
  if (-not $haveModel) {
    # models\Qwen3.5-0.8B 在 Windows 看是 WSL 符号链接，需建真实目录并从 WSL 复制
    Info "从 WSL 复制模型（约 1.7GB，请稍候）…"
    $wsl = (Get-Command wsl -ErrorAction SilentlyContinue)
    if ($wsl) {
      # 先删可能存在的符号链接/空目录，建真实目录
      cmd /c "if exist `"$ModelDir`" rmdir /s /q `"$ModelDir`" 2>nul"
      New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
      # 把 Windows 路径转成 WSL 路径：D:\Linux\... -> /mnt/d/Linux/...
      $drive = $ModelDir.Substring(0,1).ToLower()
      $rest = $ModelDir.Substring(2) -replace '\\','/'
      $winDst = "/mnt/$drive$rest"
      $src = "/home/dayrker/.cache/modelscope/hub/models/Qwen/Qwen3___5-0___8B"
      & wsl -e bash -lc "cp -Lr '$src/.' '$winDst/' 2>/dev/null"
      $haveModel = (Test-Path (Join-Path $ModelDir "config.json"))
    }
    if (-not $haveModel) {
      Warn "自动复制未成功。请手动把 WSL 里的模型目录复制到：$ModelDir"
      Warn "（资源管理器打开 \\wsl.localhost\<发行版>\home\dayrker\.cache\modelscope\hub\models\Qwen\Qwen3___5-0___8B）"
    } else { Ok "模型复制完成 → $ModelDir" }
  } else { Ok "已存在本地模型：$ModelDir" }
}

# ---------- Step 5：生成立绘（若缺）----------
$SpriteManifest = Join-Path $Root "assets\sprites\default\manifest.json"
if (-not (Test-Path $SpriteManifest)) {
  Info "生成默认立绘…"
  & $VPy (Join-Path $Root "scripts\generate_sprites.py")
}
Ok "立绘就绪"

# ---------- Step 6：写 config.json（安全合并）----------
Info "写入配置（backend=$Backend）…"
$cfgPath = Join-Path $Root "config.json"
try {
  $cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch { $cfg = [PSCustomObject]@{} }
if (-not $cfg.model) { $cfg | Add-Member -NotePropertyName model -NotePropertyValue ([PSCustomObject]@{}) -Force }
$cfg.model.enabled = $true
$cfg.model.backend = $Backend
if ($Backend -eq "ollama") {
  if (-not $cfg.model.ollama) {
    $cfg.model | Add-Member -NotePropertyName ollama -NotePropertyValue ([PSCustomObject]@{
      host = "http://127.0.0.1:11434"; model = $OllamaModel; keep_alive = "5m"; request_timeout = 60
    }) -Force
  } else { $cfg.model.ollama.model = $OllamaModel }
}
$cfg | ConvertTo-Json -Depth 12 | Set-Content -Path $cfgPath -Encoding UTF8
Ok "配置已写入 $cfgPath"

# ---------- Step 7：启动器 + 快捷方式 ----------
$Launcher = Join-Path $Root "windows\run_dolores.bat"
$pyw = Join-Path $VenvDir "Scripts\pythonw.exe"
$launcherContent = @"
@echo off
REM 由安装脚本生成/校准的启动器。无控制台窗口启动 Dolores。
start "" "$pyw" "$Root\run.py"
"@
Set-Content -Path $Launcher -Value $launcherContent -Encoding ASCII
Ok "启动器：$Launcher"

if (-not $NoShortcut) {
  try {
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $lnk = Join-Path $Desktop "Dolores.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = $pyw
    $sc.Arguments = "`"$Root\run.py`""
    $sc.WorkingDirectory = $Root
    $ico = Join-Path $Root "assets\dolores.ico"
    if (Test-Path $ico) { $sc.IconLocation = $ico }
    $sc.Description = "Dolores 桌面萌宠"
    $sc.Save()
    Ok "桌面快捷方式：$lnk"
  } catch { Warn "创建快捷方式失败（可手动运行 run_dolores.bat）：$_" }
}

# ---------- Step 8：冒烟自检 ----------
Info "导入自检…"
& $VPy -c "import dolores.app; print('import-ok')"
if ($LASTEXITCODE -ne 0) { Warn "导入自检未通过，请检查依赖。" } else { Ok "导入自检通过" }

Write-Host ""
Ok "安装完成！后端=$Backend。双击桌面「Dolores」或运行 windows\run_dolores.bat 启动。"
