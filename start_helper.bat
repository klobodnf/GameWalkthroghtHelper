@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "ARG1=%~1"
set "ARG2=%~2"
set "ARG3=%~3"

echo =============================================
echo GameWalkthroghtHelper One-Click Launcher
echo =============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11+ and try again.
    goto :fail
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :fail
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    goto :fail
)

if not exist ".venv\.deps_ready" (
    echo [INFO] Installing project dependencies...
    python -m pip install -e .[runtime]
    if errorlevel 1 (
        echo [WARN] Full runtime install failed. Trying fallback install...
        python -m pip install -e .
        if errorlevel 1 (
            echo [ERROR] Base package installation failed.
            goto :fail
        )
        python -m pip install mss Pillow opencv-python numpy pyttsx3 PyYAML pynput requests
        if errorlevel 1 (
            echo [WARN] Optional dependencies may be incomplete. The helper will still try to run.
        )
    )
    type nul > ".venv\.deps_ready"
)

echo [INFO] Initializing database...
python -m gamewalk_helper init-db --config config/default.yaml
if errorlevel 1 (
    echo [ERROR] Failed to initialize database.
    goto :fail
)

set "ENTRY_MODE=%ARG1%"
if "%ENTRY_MODE%"=="" set "ENTRY_MODE=gui"

if /I "%ENTRY_MODE%"=="gui" (
    echo [INFO] Launching desktop GUI...
    python -m gamewalk_helper gui --config config/default.yaml
    goto :exit_check
)

if /I "%ENTRY_MODE%"=="cli" (
    set "GAME_ID=%ARG2%"
    set "RUN_MODE=%ARG3%"
    if "!RUN_MODE!"=="" set "RUN_MODE=loop"
    if "!GAME_ID!"=="" (
        echo [ERROR] CLI mode requires game_id.
        echo Usage: start_helper.bat cli ^<game_id^> [once^|loop]
        goto :fail
    )

    echo [INFO] game-id: !GAME_ID!
    echo [INFO] mode: !RUN_MODE!
    if /I "!RUN_MODE!"=="once" (
        python -m gamewalk_helper run-once --config config/default.yaml --game-id "!GAME_ID!"
    ) else (
        python -m gamewalk_helper run-loop --config config/default.yaml --game-id "!GAME_ID!"
    )
    goto :exit_check
)

echo [ERROR] Unknown mode: %ENTRY_MODE%
echo Usage:
echo   start_helper.bat
echo   start_helper.bat gui
echo   start_helper.bat cli ^<game_id^> [once^|loop]
goto :fail

:exit_check
set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="0" (
    echo [INFO] Finished.
    exit /b 0
)
echo [ERROR] Command failed with code %EXITCODE%.
goto :fail

:fail
echo.
echo Press any key to exit...
pause >nul
exit /b 1
