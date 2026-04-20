@echo off
title Simulador Interactivo V1 (DAG N-Maquinas) - RPK NEXUS
set "PROJECT_ROOT=%~dp0"
set "NEXUS_ROOT=%PROJECT_ROOT%..\\"

:: Asegurar checkout de la version V1 experimental antes de arrancar
echo [Git] Cambiando a la version V1 Experimental (feature/simulador-dag-n-maquinas)...
cd /d "%PROJECT_ROOT%"
git checkout feature/simulador-dag-n-maquinas

:: Rutas a los entornos portables
set "PYTHON_EXE=%NEXUS_ROOT%_SISTEMA\runtime_python\python.exe"
set "NODE_PATH=%NEXUS_ROOT%_SISTEMA\runtime_node"
set "PATH=%NODE_PATH%;%PATH%"

echo ============================================
echo  SIMULADOR INTERACTIVO RPK NEXUS (V1)
echo ============================================
echo.

:: Instalar dependencias Python si no estan (solo la primera vez)
echo [0/3] Verificando dependencias Python...
"%PYTHON_EXE%" -m pip install fastapi uvicorn pydantic --quiet --disable-pip-version-check

echo.
echo [1/3] Arrancando Backend Python (FastAPI)...
cd /d "%PROJECT_ROOT%backend"
start "Backend Simulador" cmd /k ""%PYTHON_EXE%" server.py"

echo [2/3] Arrancando Frontend Next.js (Install + Dev)...
cd /d "%PROJECT_ROOT%frontend"
call npm install
start "Frontend Simulador" cmd /k "npm run dev"

echo [3/3] Esperando que compilen los servicios...
timeout /t 8 /nobreak >nul

start http://localhost:3000

echo.
echo Listo! La aplicacion ya esta disponible en http://localhost:3000
exit
