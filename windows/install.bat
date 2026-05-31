@echo off
REM Dolores 一键安装（Windows）。双击本文件即可。
REM 实际逻辑在 install.ps1，这里只负责以放开执行策略的方式调用它。
setlocal
echo ============================================
echo   Dolores 桌面萌宠 - Windows 一键安装
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if "%ERR%"=="0" (
  echo 安装流程结束。可在桌面找到「Dolores」快捷方式启动～
) else (
  echo 安装过程中出现问题（错误码 %ERR%）。请把上面的输出发给作者排查。
)
echo.
pause
endlocal
