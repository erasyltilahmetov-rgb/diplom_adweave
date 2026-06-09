@echo off
chcp 65001 >nul
setlocal

echo.
echo  AdWeave — Первый запуск
echo  =======================
echo.

REM ── Проверка Docker ────────────────────────────────────────
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker не найден.
    echo Установи Docker Desktop: https://www.docker.com/products/docker-desktop/
    echo После установки перезапусти этот скрипт.
    pause & exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop не запущен. Запусти его и повтори.
    pause & exit /b 1
)

echo [OK] Docker найден.

REM ── .env ───────────────────────────────────────────────────
if not exist ".env" (
    echo.
    echo [!] Файл .env не найден — создаю из шаблона...
    copy ".env.example" ".env" >nul
    echo.
    echo  ВАЖНО: Открой .env и заполни секретные ключи:
    echo    SECRET_KEY      — любая длинная случайная строка
    echo    THREADS_APP_ID  — из Meta Developers
    echo    THREADS_APP_SECRET
    echo.
    echo  Нажми любую клавишу после заполнения .env ...
    pause >nul
)

REM ── Папка для браузерного профиля ─────────────────────────
if not exist "data\browser_profile" (
    mkdir "data\browser_profile"
    echo [OK] Создана папка data\browser_profile
)

REM ── Сборка и запуск ────────────────────────────────────────
echo.
echo [1/2] Собираю образы (первый раз займёт 3-5 минут)...
docker compose build

echo.
echo [2/2] Запускаю контейнеры...
docker compose up -d

echo.
echo  Жду запуска (30 сек)...
timeout /t 30 /nobreak >nul

REM ── Публичный URL ──────────────────────────────────────────
echo.
echo  Публичный URL (Cloudflare Tunnel):
docker logs adweave_tunnel 2>&1 | findstr "trycloudflare.com"

echo.
echo  Локально: http://localhost:8000
echo  Логин:    admin / admin123
echo.
echo  Готово! Для ежедневного запуска используй start.bat
echo.
pause
endlocal
