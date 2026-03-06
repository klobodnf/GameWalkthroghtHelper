@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

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

set "ARG1=%~1"
set "ARG2=%~2"
set "GAME_ID="
set "RUN_MODE=loop"

if /I "%ARG1%"=="once" (
    set "RUN_MODE=once"
) else if /I "%ARG1%"=="loop" (
    set "RUN_MODE=loop"
) else (
    set "GAME_ID=%ARG1%"
    if not "%ARG2%"=="" set "RUN_MODE=%ARG2%"
)

if "%GAME_ID%"=="" (
    echo [INFO] Scanning Steam library and importing installed games...
    set "GWH_PICK_FILE=.gwh_selected_game.txt"
    if exist "%GWH_PICK_FILE%" del /f /q "%GWH_PICK_FILE%" >nul 2>nul
    python -m gamewalk_helper steam-select --config config/default.yaml --id-only > "%GWH_PICK_FILE%"
    if exist "%GWH_PICK_FILE%" (
        set /p GAME_ID=<"%GWH_PICK_FILE%"
        del /f /q "%GWH_PICK_FILE%" >nul 2>nul
    )
)
if "%GAME_ID%"=="" (
    set /p GAME_ID=Input game id ^(fallback, default: DemoGame^): 
)
if "%GAME_ID%"=="" set "GAME_ID=DemoGame"

echo [INFO] game-id: %GAME_ID%
echo [INFO] mode: %RUN_MODE%
echo.
echo Hotkeys in loop mode:
echo   Ctrl+Alt+M = mute/unmute
echo   Ctrl+Alt+P = pause/resume
echo   Ctrl+Alt+H = force hint refresh
echo   Ctrl+Alt+D = detail level
echo   Ctrl+Alt+Q = quit
echo.

if /I "%RUN_MODE%"=="once" (
    python -m gamewalk_helper run-once --config config/default.yaml --game-id "%GAME_ID%"
) else (
    python -m gamewalk_helper run-loop --config config/default.yaml --game-id "%GAME_ID%"
)

set "EXITCODE=%ERRORLEVEL%"
if "%EXITCODE%"=="0" (
    echo [INFO] Finished.
    goto :eof
)

echo [ERROR] Command failed with code %EXITCODE%.
goto :fail

:fail
echo.
echo Press any key to exit...
pause >nul
exit /b 1
