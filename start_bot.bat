@echo off
chcp 65001 >nul
echo Starting AdWeave Telegram Bot...
wsl -d Ubuntu -- bash -c "cd /mnt/d/Дипломка/Дипломная && source .venv/bin/activate && pip install python-telegram-bot anthropic -q && python tg_bot.py"
pause
