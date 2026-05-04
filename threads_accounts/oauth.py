from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse

import requests


THREADS_APP_ID = os.getenv("THREADS_APP_ID")
THREADS_APP_SECRET = os.getenv("THREADS_APP_SECRET")
THREADS_REDIRECT_URI = os.getenv("THREADS_REDIRECT_URI")
THREADS_SCOPES = os.getenv("THREADS_SCOPES", "threads_basic,threads_content_publish")
THREADS_API_BASE = os.getenv("THREADS_API_BASE", "https://graph.threads.net")
THREADS_AUTH_BASE = os.getenv("THREADS_AUTH_BASE", "https://www.threads.net/oauth/authorize")


class ThreadsOAuthError(RuntimeError):
    pass


@dataclass
class ThreadsOAuthResult:
    access_token: str
    user_id: str | None
    username: str | None
    expires_in: int | None


def _ensure_configured() -> None:
    missing: list[str] = []
    if not THREADS_APP_ID:
        missing.append("THREADS_APP_ID")
    if not THREADS_APP_SECRET:
        missing.append("THREADS_APP_SECRET")
    if not THREADS_REDIRECT_URI:
        missing.append("THREADS_REDIRECT_URI")
    if missing:
        raise ThreadsOAuthError(
            "Не настроены переменные окружения для OAuth: " + ", ".join(missing)
        )

    parsed = urlparse(THREADS_REDIRECT_URI or "")
    if parsed.scheme != "https":
        raise ThreadsOAuthError(
            "THREADS_REDIRECT_URI должен начинаться с https:// (Threads блокирует http)."
        )
    if "xxxx.trycloudflare.com" in (THREADS_REDIRECT_URI or ""):
        raise ThreadsOAuthError(
            "В THREADS_REDIRECT_URI стоит заглушка xxxx.trycloudflare.com. Нужен реальный домен туннеля."
        )


def build_authorize_url(state: str) -> str:
    _ensure_configured()
    query = urlencode(
        {
            "client_id": THREADS_APP_ID,
            "redirect_uri": THREADS_REDIRECT_URI,
            "scope": THREADS_SCOPES,
            "response_type": "code",
            "state": state,
        }
    )
    return f"{THREADS_AUTH_BASE}?{query}"


def exchange_code_for_token(code: str) -> dict[str, Any]:
    _ensure_configured()
    url = f"{THREADS_API_BASE}/oauth/access_token"
    params = {
        "client_id": THREADS_APP_ID,
        "client_secret": THREADS_APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": THREADS_REDIRECT_URI,
        "code": code,
    }
    response = requests.post(url, params=params, timeout=30)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ThreadsOAuthError(response.text) from exc
    return response.json()


def exchange_for_long_lived_token(short_lived_token: str) -> dict[str, Any]:
    _ensure_configured()
    url = f"{THREADS_API_BASE}/access_token"
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": THREADS_APP_SECRET,
        "access_token": short_lived_token,
    }
    response = requests.get(url, params=params, timeout=30)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ThreadsOAuthError(response.text) from exc
    return response.json()


def fetch_me(access_token: str) -> dict[str, Any]:
    url = f"{THREADS_API_BASE}/me"
    params = {
        "fields": "id,username",
        "access_token": access_token,
    }
    response = requests.get(url, params=params, timeout=30)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ThreadsOAuthError(response.text) from exc
    return response.json()


def complete_oauth(code: str) -> ThreadsOAuthResult:
    token_data = exchange_code_for_token(code)
    access_token = token_data.get("access_token")
    user_id = token_data.get("user_id")

    if not access_token:
        raise ThreadsOAuthError(f"Неожиданный ответ при обмене токена: {token_data}")

    expires_in: int | None = token_data.get("expires_in")

    try:
        long_lived = exchange_for_long_lived_token(access_token)
        access_token = long_lived.get("access_token", access_token)
        expires_in = long_lived.get("expires_in", expires_in)
    except ThreadsOAuthError:
        # Если не удалось обменять на long-lived, продолжаем с short-lived.
        pass

    me = fetch_me(access_token)
    username = me.get("username")

    return ThreadsOAuthResult(
        access_token=access_token,
        user_id=str(user_id) if user_id is not None else None,
        username=username,
        expires_in=int(expires_in) if expires_in is not None else None,
    )
