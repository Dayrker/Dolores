<#
  Dolores Desktop Pet - Windows one-click installer
  Steps:
    1. Find/install real Python (winget Python 3.12 if missing)
    2. Create .venv and install deps (Pillow required)
    3. Backend setup:
         - ollama (default): install Ollama + pull a small model + write config
         - transformers: install torch/transformers + copy local Qwen3.5 from WSL
    4. Generate sprites if missing
    5. Write config.json (merge, keep other user settings)
    6. Create launcher run_dolores.bat + Desktop shortcut
    7. Import smoke test

  Usage (in windows\ or double-click install.bat):
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

# ---------- Step 0: locate project root ----------
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Info "Project root: $Root"
Set-Location $Root

# ---------- Step 1: find/install real Python ----------
function Test-RealPython($exe) {
  if (-not $exe) { return $false }
  if ($exe -like "*WindowsApps*") { return $false }  # Microsoft Store stub
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
  # py launcher fallback
  $pylauncher = (Get-Command py -ErrorAction SilentlyContinue)
  if ($pylauncher -and ($pylauncher.Source -notlike "*WindowsApps*")) { return "py" }
  return $null
}

$Python = Find-Python
if (-not $Python) {
  Info "No usable Python found; installing Python 3.12 via winget..."
  winget install -e --id Python.Python.3.12 --source winget `
    --accept-package-agreements --accept-source-agreements
  if ($LASTEXITCODE -ne 0) { Die "Python install failed. Please install Python 3.12 manually and retry." }
  Start-Sleep -Seconds 3
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path", "User")
  $Python = Find-Python
  if (-not $Python) { Die "Still no Python after install; reopen terminal and rerun this script." }
}
Ok "Using Python: $Python"

# ---------- Step 2: create venv ----------
$VenvDir = Join-Path $Root ".venv"
$VPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VPy)) {
  Info "Creating virtual env .venv ..."
  if ($Python -eq "py") { & py -3 -m venv $VenvDir } else { & $Python -m venv $VenvDir }
  if (-not (Test-Path $VPy)) { Die "venv creation failed." }
}
Ok "venv ready: $VenvDir"

# ---------- Step 3: install Python deps ----------
Info "Upgrading pip..."
& $VPy -m pip install --upgrade pip --quiet
Info "Installing Pillow (required)..."
& $VPy -m pip install --quiet Pillow
if ($LASTEXITCODE -ne 0) { Die "Pillow install failed (check network/proxy)." }

if ($Backend -eq "transformers") {
  # RTX 50-series (Blackwell, sm_120) needs cu128 wheels; cu124 reports sm_120 incompatible.
  Info "Installing torch (cu128, for RTX 50-series) + transformers (CPU fallback on failure)..."
  & $VPy -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cu128
  if ($LASTEXITCODE -ne 0) {
    Warn "CUDA(cu128) torch install failed; installing CPU build (slower generation)..."
    & $VPy -m pip install --quiet torch
  }
  & $VPy -m pip install --quiet transformers safetensors
  if ($LASTEXITCODE -ne 0) { Die "transformers install failed." }
  Ok "transformers backend deps ready"
}
Ok "Python deps installed"

# ---------- Step 4: backend setup ----------
if ($Backend -eq "ollama") {
  Info "Setting up Ollama backend..."
  $ollama = (Get-Command ollama -ErrorAction SilentlyContinue)
  if (-not $ollama) {
    Info "Ollama not found; installing via winget..."
    winget install -e --id Ollama.Ollama --source winget `
      --accept-package-agreements --accept-source-agreements
    Start-Sleep -Seconds 3
    $env:Path += ";$env:LocalAppData\Programs\Ollama"
  }
  # start ollama service if not running
  try {
    Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null
  } catch {
    Info "Starting Ollama service..."
    Start-Process -WindowStyle Hidden -FilePath "ollama" -ArgumentList "serve" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
  }
  Info "Pulling model $OllamaModel (first time is slow)..."
  & ollama pull $OllamaModel
  if ($LASTEXITCODE -ne 0) {
    Warn "Pull $OllamaModel failed; trying fallback qwen2.5:0.5b ..."
    $OllamaModel = "qwen2.5:0.5b"
    & ollama pull $OllamaModel
    if ($LASTEXITCODE -ne 0) { Warn "Ollama model pull failed; Dolores will still run with the template brain." }
  }
  Ok "Ollama backend ready (model: $OllamaModel)"
}

if ($Backend -eq "transformers") {
  Info "Preparing local Qwen3.5 model files..."
  $ModelDir = Join-Path $Root "models\Qwen3.5-0.8B"
  $haveModel = (Test-Path (Join-Path $ModelDir "config.json"))
  if (-not $haveModel) {
    # models\Qwen3.5-0.8B is a WSL symlink (unreadable from Windows): make a real dir and copy from WSL
    Info "Copying model from WSL (~1.7GB, please wait)..."
    $wsl = (Get-Command wsl -ErrorAction SilentlyContinue)
    if ($wsl) {
      cmd /c "if exist `"$ModelDir`" rmdir /s /q `"$ModelDir`" 2>nul"
      New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
      # Windows path -> WSL path: D:\Linux\... -> /mnt/d/Linux/...
      $drive = $ModelDir.Substring(0,1).ToLower()
      $rest = $ModelDir.Substring(2) -replace '\\','/'
      $winDst = "/mnt/$drive$rest"
      $src = "/home/dayrker/.cache/modelscope/hub/models/Qwen/Qwen3___5-0___8B"
      & wsl -e bash -lc "cp -Lr '$src/.' '$winDst/' 2>/dev/null"
      $haveModel = (Test-Path (Join-Path $ModelDir "config.json"))
    }
    if (-not $haveModel) {
      Warn "Auto-copy did not succeed. Please copy the WSL model dir manually to: $ModelDir"
      Warn "(Open in Explorer: \\wsl.localhost\<distro>\home\dayrker\.cache\modelscope\hub\models\Qwen\Qwen3___5-0___8B)"
    } else { Ok "Model copied -> $ModelDir" }
  } else { Ok "Local model already present: $ModelDir" }
}

# ---------- Step 5: generate sprites if missing ----------
$SpriteManifest = Join-Path $Root "assets\sprites\default\manifest.json"
if (-not (Test-Path $SpriteManifest)) {
  Info "Generating default sprites..."
  & $VPy (Join-Path $Root "scripts\generate_sprites.py")
}
Ok "Sprites ready"

# ---------- Step 6: write config.json (safe merge) ----------
Info "Writing config (backend=$Backend)..."
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
Ok "Config written: $cfgPath"

# ---------- Step 7: launcher + shortcut ----------
$Launcher = Join-Path $Root "windows\run_dolores.bat"
$pyw = Join-Path $VenvDir "Scripts\pythonw.exe"
$launcherContent = @"
@echo off
REM Generated/calibrated launcher. Starts Dolores with no console window.
start "" "$pyw" "$Root\run.py"
"@
Set-Content -Path $Launcher -Value $launcherContent -Encoding ASCII
Ok "Launcher: $Launcher"

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
    $sc.Description = "Dolores Desktop Pet"
    $sc.Save()
    Ok "Desktop shortcut: $lnk"
  } catch { Warn "Failed to create shortcut (you can run run_dolores.bat manually): $_" }
}

# ---------- Step 8: import smoke test ----------
Info "Import smoke test..."
& $VPy -c "import dolores.app; print('import-ok')"
if ($LASTEXITCODE -ne 0) { Warn "Import smoke test failed; check dependencies." } else { Ok "Import smoke test passed" }

Write-Host ""
Ok "Install complete! backend=$Backend. Double-click the Desktop 'Dolores' shortcut or run windows\run_dolores.bat."
