@echo off
title RPK NEXUS V6 - Full Stack Launcher
color 0A

echo ============================================
echo   RPK NEXUS V6 - Arranque Completo
echo ============================================
echo.

set ROOT=%~dp0
set PYTHON=%ROOT%_SISTEMA\runtime_python\python.exe
set NODE=%ROOT%_SISTEMA\runtime_node\node.exe
set NPM=%ROOT%_SISTEMA\runtime_node\npm.cmd

echo [1/2] Arrancando Backend Python (FastAPI) en :8000...
start "NEXUS Backend (FastAPI :8000)" cmd /k "title NEXUS Backend & color 0E & echo === BACKEND PYTHON === & "%PYTHON%" -m uvicorn backend.server_nexus:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo [2/2] Arrancando Frontend React (Next.js) en :3000...
start "NEXUS Frontend (React :3000)" cmd /k "title NEXUS Frontend & color 0B & echo === FRONTEND REACT === & cd nexus-v6 & set PATH=%ROOT%_SISTEMA\runtime_node;%%PATH%% & "%NPM%" run dev"

timeout /t 5 /nobreak > nul

echo.
echo ============================================
echo   TODO ARRANCADO
echo ============================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000  (abrir aqui)
echo.
echo   Cierra las ventanas para detener.
echo ============================================

start http://localhost:3000

exit
