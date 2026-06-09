@echo off
setlocal
set ROOT=%~dp0

echo ===========================================
echo   AdWeave — Cloudflare Tunnel
echo ===========================================
echo.

REM Ищем Python
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python
    goto :run
)

where python3 >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python3
    goto :run
)

echo Ошибка: Python не найден. Установи Python 3.
pause
exit /b 1

:run
echo Запускаю туннель...
echo Django должен работать на http://127.0.0.1:8000
echo.
%PYTHON_CMD% "%ROOT%scripts\quick_tunnel.py"

if errorlevel 1 (
    echo.
    echo Ошибка: туннель не запустился.
    echo Проверь что cloudflared установлен:
    echo   winget install Cloudflare.cloudflared
)

pause
endlocal
