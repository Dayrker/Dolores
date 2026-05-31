<#  Dolores 卸载：移除 .venv 与桌面快捷方式（保留模型与配置）。 #>
$ErrorActionPreference = "SilentlyContinue"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "[*] 移除虚拟环境 .venv …"
Remove-Item -Recurse -Force (Join-Path $Root ".venv")
$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "Dolores.lnk"
if (Test-Path $lnk) { Remove-Item -Force $lnk; Write-Host "[*] 已删除桌面快捷方式" }
Write-Host "[OK] 卸载完成（models/ 与 config.json 已保留）。"
