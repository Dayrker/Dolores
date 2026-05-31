@echo off
REM Dolores one-click installer (Windows). Double-click to run.
REM Real logic is in install.ps1; this just calls it with relaxed execution policy.
setlocal
echo ============================================
echo   Dolores Desktop Pet - Windows Installer
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if "%ERR%"=="0" (
  echo Done. Look for the "Dolores" shortcut on your Desktop.
) else (
  echo Something went wrong (error code %ERR%). Please send the output above to the author.
)
echo.
pause
endlocal
