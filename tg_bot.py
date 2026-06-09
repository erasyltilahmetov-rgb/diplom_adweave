import subprocess, re, os, asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TG_TOKEN = "8250873717:AAEnClwyEbtgJi4U4BRSzDfxcGAtYwuCCiQ"
TG_CHAT  = -4804805555

COMPOSE_DIR = "/mnt/d/Дипломка/Дипломная"

def only_owner(func):
    async def wrapper(update: Update, ctx):
        if update.effective_chat.id != TG_CHAT:
            return
        await func(update, ctx)
    return wrapper

def run(cmd: str, timeout=120) -> str:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            cwd=COMPOSE_DIR
        )
        out = (r.stdout + r.stderr).strip()
        return out[:3000] if out else "(нет вывода)"
    except subprocess.TimeoutExpired:
        return "Timeout — команда выполняется слишком долго"
    except Exception as e:
        return f"Ошибка: {e}"

def get_url() -> str:
    started = run("docker inspect adweave_tunnel --format '{{.State.StartedAt}}'").strip().strip("'")
    print(f"[get_url] tunnel started at: {started!r}")
    if started and started != "(нет вывода)":
        out = run(f"docker logs adweave_tunnel --since {started} 2>&1")
    else:
        out = run("docker logs adweave_tunnel --tail 100 2>&1")
    print(f"[get_url] output_len={len(out)} preview={out[:300]!r}")
    urls = re.findall(r"https://[\w-]+\.trycloudflare\.com", out)
    if urls:
        print(f"[get_url] found: {urls[-1]}")
        return urls[-1]
    print("[get_url] no URL found")
    return ""

def is_web_running() -> bool:
    status = run("docker inspect adweave_web --format '{{.State.Status}}'").strip().strip("'")
    return status == "running"

# ── Watchdog ────────────────────────────────────────────────────────────────
async def watchdog_loop(bot):
    """Каждые 5 минут проверяет контейнер. Если упал — перезапускает."""
    await asyncio.sleep(60)  # дать боту стартануть
    print("[watchdog] запущен, проверка каждые 5 мин")
    while True:
        try:
            if not is_web_running():
                print("[watchdog] adweave_web упал, перезапускаю...")
                await bot.send_message(TG_CHAT, "⚠️ Сайт упал. Перезапускаю...")
                run("docker compose up -d")
                await asyncio.sleep(40)
                url = get_url()
                msg = f"✅ Перезапущен! {url}" if url else "✅ Перезапущен. Используй /url для ссылки."
                await bot.send_message(TG_CHAT, msg)
        except Exception as e:
            print(f"[watchdog] ошибка: {e}")
        await asyncio.sleep(300)  # пауза 5 мин

async def post_init(application):
    asyncio.create_task(watchdog_loop(application.bot))

# ── Команды ─────────────────────────────────────────────────────────────────

@only_owner
async def cmd_start(update: Update, ctx):
    msg = await update.message.reply_text("▶️ Запускаю контейнеры...")
    out = run("docker compose up -d --no-recreate")
    await msg.edit_text(f"✅ Запущено:\n```\n{out[:800]}\n```", parse_mode="Markdown")

    url_msg = await update.message.reply_text("⏳ Жду публичный URL...")
    url = ""
    for _ in range(30):
        await asyncio.sleep(3)
        url = get_url()
        if url:
            break
    if url:
        await url_msg.edit_text(f"🌐 Сайт доступен: {url}")
    else:
        await url_msg.edit_text("URL не найден. Попробуй /url через 30 сек.")

@only_owner
async def cmd_stop(update: Update, ctx):
    msg = await update.message.reply_text("⏹ Останавливаю...")
    out = run("docker compose down")
    await msg.edit_text(f"🛑 Остановлено:\n```\n{out[:800]}\n```", parse_mode="Markdown")

@only_owner
async def cmd_restart(update: Update, ctx):
    msg = await update.message.reply_text("🔄 Перезапускаю...")
    out = run("docker compose restart")
    await msg.edit_text(f"✅ Перезапущено:\n```\n{out[:800]}\n```", parse_mode="Markdown")

    url_msg = await update.message.reply_text("⏳ Жду новый URL...")
    url = ""
    for _ in range(30):
        await asyncio.sleep(3)
        url = get_url()
        if url:
            break
    await url_msg.edit_text(f"🌐 {url}" if url else "URL не найден, попробуй /url")

@only_owner
async def cmd_url(update: Update, ctx):
    url = get_url()
    if url:
        await update.message.reply_text(f"🌐 {url}")
    else:
        await update.message.reply_text("URL не найден. Туннель ещё стартует?")

@only_owner
async def cmd_status(update: Update, ctx):
    out = run("docker compose ps")
    await update.message.reply_text(f"📊 Статус:\n```\n{out}\n```", parse_mode="Markdown")

@only_owner
async def cmd_logs(update: Update, ctx):
    out = run("docker logs adweave_web --tail=40 2>&1")
    await update.message.reply_text(f"```\n{out[-2000:]}\n```", parse_mode="Markdown")

@only_owner
async def cmd_login(update: Update, ctx):
    """Авто-логин в Threads через сохранённые учётные данные из .env"""
    msg = await update.message.reply_text("🔐 Запускаю авто-логин в Threads...")
    out = run(
        "docker exec adweave_web python /app/ai_generator/auto_login.py 2>&1",
        timeout=180
    )
    icon = "✅" if "успешно" in out.lower() or "already" in out.lower() else "❌"
    await msg.edit_text(f"{icon} Результат:\n```\n{out[:1500]}\n```", parse_mode="Markdown")

@only_owner
async def cmd_watchdog(update: Update, ctx):
    """Включить/выключить статус watchdog"""
    running = is_web_running()
    await update.message.reply_text(
        f"🔍 Watchdog активен — проверяет каждые 5 мин.\n"
        f"Текущий статус adweave\\_web: {'✅ running' if running else '❌ НЕ запущен'}"
    )

@only_owner
async def cmd_help(update: Update, ctx):
    await update.message.reply_text(
        "📋 *Команды AdWeave*\n\n"
        "/start\\_server — запустить всё\n"
        "/stop — остановить всё\n"
        "/restart — перезапустить\n"
        "/url — получить ссылку на сайт\n"
        "/status — состояние контейнеров\n"
        "/logs — последние логи Django\n"
        "/login — авто-логин в Threads\n"
        "/watchdog — статус авто-мониторинга\n"
        "/help — это сообщение\n\n"
        "🔁 *Watchdog*: бот сам перезапустит сайт если он упадёт.",
        parse_mode="Markdown"
    )

app = (
    ApplicationBuilder()
    .token(TG_TOKEN)
    .post_init(post_init)
    .build()
)
app.add_handler(CommandHandler("start_server", cmd_start))
app.add_handler(CommandHandler("stop",         cmd_stop))
app.add_handler(CommandHandler("restart",      cmd_restart))
app.add_handler(CommandHandler("url",          cmd_url))
app.add_handler(CommandHandler("status",       cmd_status))
app.add_handler(CommandHandler("logs",         cmd_logs))
app.add_handler(CommandHandler("login",        cmd_login))
app.add_handler(CommandHandler("watchdog",     cmd_watchdog))
app.add_handler(CommandHandler("help",         cmd_help))

print("AdWeave bot running.")
print("Commands: /start_server /stop /restart /url /status /logs /login /watchdog /help")
print("Watchdog: автоматически перезапускает сайт если он упал.")
app.run_polling()
