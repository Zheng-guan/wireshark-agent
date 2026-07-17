@echo off
chcp 65001 >nul
title Wireshark Agent - Web
REM ============================================================
REM  Wireshark Agent (Web Edition) - Windows Launcher
REM  Starts FastAPI backend + React frontend, then opens browser.
REM  NOTE: Pure ASCII only - do NOT add Chinese characters.
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo   Wireshark Agent (Web Edition) - Starting...
echo ============================================================

REM ---- 1. Check Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

REM ---- 2. Check Node.js ----
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm not found. Please install Node.js 18+ and add to PATH.
    pause
    exit /b 1
)

REM ---- 3. Install Python deps on first run ----
python -c "import fastapi, uvicorn, langchain, pyshark" >nul 2>nul
if errorlevel 1 (
    echo [INFO] First run, installing Python dependencies, please wait...
    pip install -r backend\requirements.txt
    pip install -e pyshark-master\src
    if errorlevel 1 (
        echo [WARN] Python deps install may have failed, continuing anyway.
    ) else (
        echo [INFO] Python dependencies installed.
    )
) else (
    echo [INFO] Python dependencies ready, skip install.
)

REM ---- 4. Install frontend deps on first run ----
if not exist "frontend\node_modules" (
    echo [INFO] First run, installing frontend dependencies, please wait...
    pushd frontend
    call npm install
    popd
) else (
    echo [INFO] Frontend dependencies ready, skip install.
)

REM ---- 5. Check .env config ----
if not exist "backend\.env" (
    if exist "wireshark_llm_agent\.env" (
        copy "wireshark_llm_agent\.env" "backend\.env" >nul
        echo [INFO] Copied .env from wireshark_llm_agent to backend.
    ) else (
        echo [WARN] backend\.env not found. Please create it with:
        echo        TSHARK_PATH=E:\Wireshark\tshark.exe
        echo        ZHIPUAI_API_KEY=your_key
    )
) else (
    echo [INFO] .env config found.
)

REM ---- 6. Start backend (new window) ----
echo [INFO] Starting FastAPI backend on http://127.0.0.1:8000 ...
start "Wireshark Agent Backend" cmd /k "cd /d %~dp0backend && python main.py"

REM ---- 7. Start frontend (new window) ----
echo [INFO] Starting React frontend on http://localhost:5173 ...
start "Wireshark Agent Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

REM ---- 8. Open browser ----
timeout /t 6 /nobreak >nul
echo [INFO] Opening browser at http://localhost:5173
start http://localhost:5173

echo.
echo ============================================================
echo   Both services started in separate windows.
echo   Close those windows to stop the services.
echo ============================================================
pause
