<#  Dolores uninstall: remove .venv and the Desktop shortcut (keeps models and config). #>
$ErrorActionPreference = "SilentlyContinue"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "[*] Removing virtual env .venv ..."
Remove-Item -Recurse -Force (Join-Path $Root ".venv")
$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Dolores.lnk"
if (Test-Path $lnk) { Remove-Item -Force $lnk; Write-Host "[*] Removed Desktop shortcut" }
Write-Host "[OK] Uninstalled (models/ and config.json kept)."
