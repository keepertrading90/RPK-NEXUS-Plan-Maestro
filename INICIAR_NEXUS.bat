@echo off
title RPK NEXUS - Centro de Control Unificado
setlocal

:: Configuración de colores (RPK Style)
color 0C

echo ============================================================
echo        RPK NEXUS : PORTAL DE CONTROL INTELIGENTE
echo ============================================================
echo.

:: 1. Sincronizar datos
echo [PASO 1] Sincronizando datos unificados desde la red (Y:)...
start /wait "" ".\_SISTEMA\runtime_python\python.exe" scripts/sync_nexus.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ ERROR: No se han podido sincronizar los datos.
    echo Verifique su conexion a la unidad Y:
    pause
    exit /b
)

echo.
echo [PASO 2] Lanzando Servidor Nexus Hub y Portal Web...
echo.

:: 2. Iniciar el servidor API y la UI en segundo plano
:: El servidor abrirá la web en http://localhost:8000
start "" ".\_SISTEMA\runtime_python\python.exe" backend/server_nexus.py

:: 3. Abrir Navegador Automáticamente (pequeña espera para que el server suba)
timeout /t 3 /nobreak > nul
start http://localhost:8000

echo.
echo NEXUS HUB esta activo en: http://localhost:8000
echo.
echo [PASO 3] Iniciando Asistente de Consultas CLI (Secundario)...
echo.
".\_SISTEMA\runtime_python\python.exe" backend/db/consultor.py

echo.
echo ============================================================
echo   NEXUS HUB FINALIZADO
echo ============================================================
pause
