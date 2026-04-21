@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%SCRIPT_DIR%command-failure-memory.py" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%SCRIPT_DIR%command-failure-memory.py" %*
  exit /b %ERRORLEVEL%
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%command-failure-memory.ps1" %*
exit /b %ERRORLEVEL%
