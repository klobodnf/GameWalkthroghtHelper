@echo off
setlocal EnableExtensions

cd /d "%~dp0"
echo =============================================
echo Configure AI Provider (GameWalkthroghtHelper)
echo =============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\set-ai-provider.ps1" %*
set "EXITCODE=%ERRORLEVEL%"

if "%EXITCODE%"=="0" (
  echo.
  echo [INFO] Configuration completed.
  exit /b 0
)

echo.
echo [ERROR] Configuration failed. code=%EXITCODE%
echo Press any key to exit...
pause >nul
exit /b %EXITCODE%
