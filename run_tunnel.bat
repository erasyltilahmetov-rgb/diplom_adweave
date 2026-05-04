@echo off
setlocal

REM Запуск quick tunnel + авто-обновление .env и site.txt
set ROOT=%~dp0
set PYTHON_EXE=%ROOT%.venv\Scripts\python.exe

if exist "%PYTHON_EXE%" (
  set PYTHON_CMD="%PYTHON_EXE%"
) else (
  set PYTHON_CMD=python
)

echo Using %PYTHON_CMD%
%PYTHON_CMD% "%ROOT%scripts\quick_tunnel.py"

if errorlevel 1 (
  echo.
  echo Ошибка: не удалось запустить туннель. Проверь, что Python и cloudflared доступны.
)

pause
endlocal
