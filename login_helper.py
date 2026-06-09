"""
Запусти этот скрипт на Windows (НЕ в Docker), чтобы войти в Threads.
Браузер откроется видимым — войди в аккаунт, затем нажми Enter.
Cookies сохранятся в папку browser_profile/ рядом с этим файлом.
Docker потом прочитает их оттуда.

Запуск:
  python login_helper.py
"""

from playwright.sync_api import sync_playwright
from pathlib import Path

profile_dir = str(Path(__file__).parent / "browser_profile")

print(f"Профиль браузера: {profile_dir}")
print("Открываю Threads в браузере...")

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=False,
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    page = browser.new_page()
    page.goto("https://www.threads.com", wait_until="domcontentloaded")

    print()
    print("===========================================")
    print("  Войди в Threads в открывшемся браузере.")
    print("  После входа вернись сюда и нажми Enter.")
    print("===========================================")
    input()

    browser.close()

print()
print("Готово! Cookies сохранены в browser_profile/")
print("Перезапусти Docker: docker compose restart web")
