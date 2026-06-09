"""
Авто-логин в Threads.
Запуск: docker exec adweave_web python /app/ai_generator/auto_login.py
"""
import os, sys, time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

PROFILE_DIR = os.getenv("BROWSER_PROFILE_DIR", "/data/browser_profile")
USERNAME    = os.getenv("THREADS_USERNAME", "").strip()
PASSWORD    = os.getenv("THREADS_PASSWORD", "").strip()


def log(msg):
    print(msg, flush=True)


def check_and_login() -> bool:
    if not USERNAME or not PASSWORD:
        log("❌ Задай THREADS_USERNAME и THREADS_PASSWORD в .env")
        return False

    log(f"🌐 Браузер запущен (профиль: {PROFILE_DIR})")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            # ── Проверка текущей сессии ───────────────────────────────────────
            log("🔍 Проверяю сессию...")
            page.goto("https://www.threads.com/", wait_until="networkidle", timeout=40000)

            if "login" not in page.url:
                log(f"✅ Уже залогинен! URL: {page.url}")
                return True

            # ── Открываем логин ───────────────────────────────────────────────
            log("🔑 Открываю страницу логина...")
            page.goto("https://www.threads.com/login/", wait_until="networkidle", timeout=40000)
            log(f"   URL: {page.url}")

            # ── Ждём появления формы ──────────────────────────────────────────
            log("   Жду форму...")
            try:
                page.wait_for_selector("input", timeout=15000)
            except PWTimeout:
                page.screenshot(path="/data/login_debug.png")
                log("❌ Форма не появилась. Скриншот: /data/login_debug.png")
                return False

            # Дать React-у отрендериться
            time.sleep(2)

            # ── Логин ─────────────────────────────────────────────────────────
            user_input = (
                page.query_selector('input[name="username"]') or
                page.query_selector('input[autocomplete="username"]') or
                page.query_selector('input[type="text"]')
            )
            if not user_input:
                page.screenshot(path="/data/login_debug.png")
                log("❌ Поле логина не найдено. Скриншот: /data/login_debug.png")
                return False

            user_input.click()
            user_input.fill("")
            page.keyboard.type(USERNAME, delay=80)
            time.sleep(0.5)
            log(f"   ✍ Логин: {USERNAME}")

            # ── Пароль ────────────────────────────────────────────────────────
            pass_input = (
                page.query_selector('input[name="password"]') or
                page.query_selector('input[type="password"]')
            )
            if not pass_input:
                page.screenshot(path="/data/login_debug.png")
                log("❌ Поле пароля не найдено. Скриншот: /data/login_debug.png")
                return False

            pass_input.click()
            pass_input.fill("")
            page.keyboard.type(PASSWORD, delay=80)
            time.sleep(0.5)
            log("   🔒 Пароль введён")

            # ── Кнопка Войти ──────────────────────────────────────────────────
            btn = (
                page.query_selector('button[type="submit"]') or
                page.query_selector('button:has-text("Log in")') or
                page.query_selector('button:has-text("Войти")')
            )
            if btn:
                btn.click()
                log("   ▶ Нажал кнопку входа")
            else:
                pass_input.press("Enter")
                log("   ▶ Отправил по Enter")

            # ── Ждём переход ──────────────────────────────────────────────────
            log("   ⏳ Жду ответа сервера...")
            try:
                page.wait_for_url(lambda u: "login" not in u, timeout=20000)
                log(f"   ✅ Навигация: {page.url}")
            except PWTimeout:
                pass

            time.sleep(3)
            url_after = page.url
            log(f"   URL итог: {url_after}")

            # 2FA?
            if page.query_selector('input[name="verificationCode"], input[aria-label*="code"]'):
                page.screenshot(path="/data/login_debug.png")
                log("⚠️ Требуется 2FA-код. Отключи двухфакторку на аккаунте.")
                return False

            if "login" in url_after:
                page.screenshot(path="/data/login_debug.png")
                log("❌ Не удалось войти. Скорее всего неверный пароль.")
                log("   Скриншот: /data/login_debug.png")
                log("   Посмотреть: docker cp adweave_web:/data/login_debug.png ./login_debug.png")
                return False

            log("✅ Успешно вошли в Threads! Сессия сохранена в browser_profile.")
            return True

        except Exception as e:
            log(f"❌ Ошибка: {e}")
            try:
                page.screenshot(path="/data/login_debug.png")
                log("   Скриншот: /data/login_debug.png")
            except Exception:
                pass
            return False
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(0 if check_and_login() else 1)
