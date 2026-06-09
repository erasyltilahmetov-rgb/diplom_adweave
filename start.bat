@echo off
chcp 65001 >nul
setlocal

echo.
echo  AdWeave — Запуск
echo  ================
echo.

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop не запущен. Запусти его и повтори.
    pause & exit /b 1
)

docker compose up -d

echo.
echo  Жду публичный URL...
set URL=
for /L %%i in (1,1,20) do (
    timeout /t 2 /nobreak >nul
    for /f "delims=" %%u in ('docker logs adweave_tunnel 2^>^&1 ^| findstr "trycloudflare.com"') do set URL=%%u
    if defined URL goto :found
)

:found
echo.
if defined URL (
    echo  Публичный: %URL%
) else (
    echo  URL не найден — проверь: docker logs adweave_tunnel
)
echo  Локально:  http://localhost:8000
echo.
echo  Остановить: docker compose down
echo.
pause
endlocal
