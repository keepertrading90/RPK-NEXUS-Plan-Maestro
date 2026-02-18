@echo off
title RPK NEXUS HUB - Centro de Control
setlocal

:: Colores RPK (Fondo negro, texto rojo)
color 0C

echo ============================================================
echo        RPK NEXUS : PORTAL DE CONTROL INTELIGENTE
echo ============================================================
echo.

:: 1. Sincronizar datos (Rápido)
echo [1/3] Sincronizando datos de produccion (Red -> Local)...
".\_SISTEMA\runtime_python\python.exe" scripts/sync_nexus.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ AVISO: Error en sincronizacion. Verifique conexion a la Red RPK.
    echo Se intentara abrir el panel con los ultimos datos locales.
    echo.
)

:: 2. Lanzar Servidor y UI
echo.
echo [PASO 2] Lanzando Servidor Nexus Hub y Portal Web...
echo.

:: Liberar puerto 8000 si está ocupado
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

:: Abrir el navegador justo después de lanzar el servidor
start http://localhost:8000

:: Iniciar el servidor en la ventana actual (esto bloqueará el BAT para mantener el servicio)
echo [3/3] PANEL ACTIVO en http://localhost:8000
echo.
echo Presione CTRL+C para apagar el servidor.
echo.
".\_SISTEMA\runtime_python\python.exe" backend/server_nexus.py

echo.
echo ============================================================
echo   NEXUS HUB FINALIZADO
echo ============================================================
pause
