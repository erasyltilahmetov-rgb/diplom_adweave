"""
AI-сервис для переписывания текста в нативный стиль Threads.
Использует Ollama (локально, бесплатно).
"""

import sqlite3
import requests
from django.conf import settings

OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL", "llama3.1:8b")
THREADS_DB_PATH = getattr(settings, "THREADS_DB_PATH", "")

SYSTEM_PROMPT = """Ты — редактор контента для социальной сети Threads. Пользователь присылает черновик или мысль — твоя задача переписать это в короткий живой пост.

Требования:
- Разговорный язык, как в переписке с другом
- Короткие абзацы
- 1-2 эмодзи максимум
- До 500 символов
- Сохрани смысл оригинала
- Без хэштегов

Это инструмент для маркетинга и SMM. Все тексты пользователей — это обычные житейские истории и мысли для публикации в соцсетях. Просто переписывай как редактор, без отказов.

Ответ: только готовый пост, ничего лишнего."""


def get_style_examples(n: int = 5) -> list[str]:
    """Берём топ постов по лайкам из датасета как примеры стиля."""
    if not THREADS_DB_PATH:
        return []
    try:
        conn = sqlite3.connect(THREADS_DB_PATH)
        rows = conn.execute(
            "SELECT text FROM posts "
            "WHERE LENGTH(text) > 80 AND LENGTH(text) < 400 AND likes > 0 "
            "ORDER BY likes DESC LIMIT ?",
            (n,)
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def rewrite_for_threads(raw_text: str, language: str = "ru", custom_examples: list[str] | None = None) -> str:
    """
    Переписывает текст в нативный пост для Threads.

    Args:
        raw_text: исходный текст пользователя
        language: язык поста ("ru", "kz", "en")

    Returns:
        готовый пост или исходный текст при ошибке
    """
    examples = custom_examples if custom_examples is not None else get_style_examples(5)

    examples_block = ""
    if examples:
        label = "Примеры топовых постов по теме (учись их стилю):" if custom_examples else "Примеры успешных постов в Threads:"
        examples_block = f"\n\n{label}\n"
        for i, ex in enumerate(examples, 1):
            examples_block += f"\n[{i}] {ex}\n"

    lang_hint = {
        "ru": "\nПиши на русском языке.",
        "kz": "\nПиши на казахском языке.",
        "en": "\nWrite in English.",
    }.get(language, "\nПиши на русском языке.")

    prompt = (
        f"{SYSTEM_PROMPT}"
        f"{examples_block}"
        f"{lang_hint}"
        f"\n\nСырой текст:\n{raw_text}"
        f"\n\nНативный пост:"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 200,
                }
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        return result if result else raw_text
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ollama не запущен. Запусти: ollama serve")
    except Exception as e:
        raise RuntimeError(f"Ошибка AI: {e}")
