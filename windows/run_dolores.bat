@echo off
REM Dolores 启动器（占位版；运行 windows\install.bat 后会被校准为绝对路径版）。
REM 优先用安装生成的 .venv，无则回退系统 Python。
setlocal
set ROOT=%~dp0..
if exist "%ROOT%\.venv\Scripts\pythonw.exe" (
  start "" "%ROOT%\.venv\Scripts\pythonw.exe" "%ROOT%\run.py"
) else (
  echo 未找到 .venv，请先双击 windows\install.bat 完成安装。
  echo 也可尝试用系统 Python 直接运行：
  echo     python "%ROOT%\run.py"
  pause
)
endlocal
