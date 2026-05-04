"""
Сбор трендовых тем из Threads в реальном времени.
Использует Playwright для скрапинга + частотный анализ слов.
"""

import re
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from django.conf import settings

THREADS_DB_PATH = getattr(settings, "THREADS_DB_PATH", "")

# Стоп-слова (русский + казахский + английский)
STOPWORDS = {
    # Русские
    "и","в","не","на","я","что","он","с","по","это","а","как","но","к","у",
    "из","за","от","то","все","она","так","его","бы","или","мне","было",
    "вот","же","ещё","нет","да","ну","уже","там","тут","если","их","ли",
    "об","будет","кто","мы","они","её","вы","нас","нам","вас","вам","им",
    "при","до","со","то","об","про","для","без","под","над","сей",
    "тебя","себя","тот","эта","эти","эту","этот","которые","который","которая",
    "когда","где","куда","откуда","почему","потому","чтобы","чем","чего","чему",
    "даже","ведь","вдруг","этого","этой","этому","этим","этих",
    "мой","моя","моё","мои","твой","твоя","наш","ваш","свой","своя",
    "один","два","три","много","мало","очень","quite","более","менее",
    "также","тоже","можно","нужно","надо","хочу","хочется","буду","был","была",
    # Казахские частые
    "және","да","ол","бұл","бар","жоқ","деп","үшін","мен","сен","біз",
    # Английские
    "the","a","an","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","could","should",
    "may","might","shall","can","need","dare","ought","used","to","of",
    "in","on","at","by","for","with","about","against","between","through",
    "i","you","he","she","it","we","they","my","your","his","her","its",
    "our","their","this","that","these","those","what","which","who","how",
    "when","where","why","not","no","so","if","but","or","and","just","get",
}

KAZAKH_CHARS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")


def detect_language(text: str) -> str:
    if any(c in KAZAKH_CHARS for c in text):
        return "kz"
    if re.search(r"[а-яёА-ЯЁ]", text):
        return "ru"
    return "en"


def extract_words(text: str) -> list[str]:
    """Извлекаем обычные значимые слова."""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\w\sЀ-ӿĀ-ɏ]", " ", text)
    words = text.lower().split()
    return [
        w for w in words
        if len(w) >= 3
        and w not in STOPWORDS
        and not w.isdigit()
    ]


def extract_entities(text: str) -> list[str]:
    """
    Извлекаем именованные сущности — слова с заглавной буквы в середине предложения,
    а также устойчивые словосочетания (биграммы с заглавными словами).
    Находит: компании, бренды, места, имена.
    """
    entities = []

    # Убираем URL
    text = re.sub(r"http\S+", "", text)

    # Ищем слова с заглавной буквы длиннее 2 символов (не начало предложения)
    # Паттерн: после пробела или в середине текста — заглавная буква
    tokens = re.findall(r"(?<=[^\.\!\?]\s)([А-ЯЁA-ZӘІҢҒҮҰҚӨҺ][а-яёa-zәіңғүұқөһА-ЯЁA-ZӘІҢҒҮҰҚӨҺ]{2,})", text)
    for t in tokens:
        if t.lower() not in STOPWORDS and len(t) >= 3:
            entities.append(t)

    # Ищем биграммы с заглавными словами (типа "Kaspi Bank", "BI Group", "Алматы Сити")
    bigram_pattern = re.findall(
        r"([А-ЯЁA-ZӘІҢҒҮҰҚӨҺ][а-яёa-zәіңғүұқөһА-ЯЁA-ZӘІҢҒҮҰҚӨҺ]{1,}\s[А-ЯЁA-ZӘІҢҒҮҰҚӨҺ][а-яёa-zәіңғүұқөһА-ЯЁA-ZӘІҢҒҮҰҚӨҺ]{1,})",
        text
    )
    for bg in bigram_pattern:
        words_in_bg = bg.split()
        if not any(w.lower() in STOPWORDS for w in words_in_bg):
            entities.append(bg)

    # Ищем латинские бренды (Kaspi, Beeline, TikTok и т.д.)
    latin_brands = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
    for brand in latin_brands:
        if brand.lower() not in STOPWORDS:
            entities.append(brand)

    return entities


def get_trending_from_db(hours: int = 24, top_n: int = 20) -> list[dict]:
    """
    Анализируем посты из базы за последние N часов.
    Быстрый путь — не требует скрапинга.
    """
    if not THREADS_DB_PATH or not Path(THREADS_DB_PATH).exists():
        return []

    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    try:
        conn = sqlite3.connect(THREADS_DB_PATH)
        rows = conn.execute(
            "SELECT text FROM posts ORDER BY RANDOM() LIMIT 5000"
        ).fetchall()
        conn.close()
    except Exception:
        return []

    entity_counter: Counter = Counter()

    for (text,) in rows:
        entities = extract_entities(text)
        entity_counter.update(entities)

    results = []
    for entity, count in entity_counter.most_common(top_n * 4):
        if count < 2:
            break
        if re.search(r"[а-яёА-ЯЁa-zA-ZәіңғүұқөһӘІҢҒҮҰҚӨҺ]{2,}", entity):
            results.append({
                "word": entity,
                "count": count,
                "lang": detect_language(entity),
                "type": "entity",
            })
        if len(results) >= top_n:
            break

    return results


def get_trending_live(top_n: int = 20) -> list[dict]:
    """
    Скрапим свежие посты из Threads прямо сейчас (30-60 сек).
    Возвращает трендовые слова из текущей ленты.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return get_trending_from_db(top_n=top_n)

    posts_text = []

    try:
        profile_dir = str(Path(THREADS_DB_PATH).parent / "browser_profile")

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = browser.new_page()

            # Перехватываем API-ответы
            def capture(response):
                if "graphql" in response.url or "/api/" in response.url:
                    try:
                        data = response.json()
                        texts = _extract_texts(data)
                        posts_text.extend(texts)
                    except Exception:
                        pass

            page.on("response", capture)
            page.goto("https://www.threads.com", timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Скроллим 10 раз чтобы загрузить посты
            for _ in range(10):
                page.keyboard.press("End")
                page.wait_for_timeout(800)

            browser.close()
    except Exception:
        # Fallback на базу данных
        return get_trending_from_db(top_n=top_n)

    if not posts_text:
        return get_trending_from_db(top_n=top_n)

    word_counter: Counter = Counter()
    for text in posts_text:
        word_counter.update(extract_words(text))

    results = []
    for word, count in word_counter.most_common(top_n * 3):
        if re.search(r"[а-яёА-ЯЁa-zA-ZәіңғүұқөһӘІҢҒҮҰҚӨҺ]{3,}", word):
            results.append({
                "word": word,
                "count": count,
                "lang": detect_language(word),
            })
        if len(results) >= top_n:
            break

    return results


def _extract_texts(obj, depth=0) -> list[str]:
    """Рекурсивно ищем текстовые поля в JSON."""
    if depth > 10:
        return []
    texts = []
    if isinstance(obj, dict):
        for key in ("text", "body", "content", "caption", "message"):
            val = obj.get(key)
            if isinstance(val, str) and 30 <= len(val) <= 500:
                texts.append(val)
            elif isinstance(val, dict):
                inner = val.get("text", "")
                if isinstance(inner, str) and 30 <= len(inner) <= 500:
                    texts.append(inner)
        for v in obj.values():
            texts.extend(_extract_texts(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(_extract_texts(item, depth + 1))
    return texts
