# Запуск AdWeave на новом ПК

## Требования
- Windows 10/11
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (включить WSL2 при установке)
- ~10 ГБ свободного места (модель Llama 3.1 скачается сама)

## Запуск

1. Распакуй архив в любую папку, например `D:\AdWeave\`

2. Открой **WSL** или **PowerShell** и перейди в папку:
   ```bash
   cd /mnt/d/AdWeave   # WSL
   # или
   cd D:\AdWeave        # PowerShell
   ```

3. Запусти:
   ```bash
   docker compose up -d
   ```

4. Подожди 5-10 минут — Ollama скачает модель Llama 3.1 (~5 ГБ)

5. Открой браузер: `http://localhost:8000`

## Войти в систему
- Логин: **admin**
- Пароль: смотри в .env файле (DJANGO_SUPERUSER_PASSWORD)

## Если нужен HTTPS (для Threads OAuth)
Cloudflare Tunnel запустится автоматически.
Ссылку смотри командой:
```bash
docker logs adweave_tunnel 2>&1 | grep trycloudflare
```
Обнови THREADS_REDIRECT_URI в .env на новый URL и перезапусти:
```bash
docker compose restart web
```

## Live Scraper (сбор постов)
При первом запуске браузер-сессия Threads пустая.
Запусти `login_helper.py` чтобы войти:
```bash
python login_helper.py
```
