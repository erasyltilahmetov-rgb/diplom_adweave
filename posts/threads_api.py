from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


RAW_API_BASE = os.getenv("THREADS_API_BASE", "https://graph.threads.net")
if "/v" not in RAW_API_BASE.rstrip("/").split("/")[-1]:
    API_BASE = RAW_API_BASE.rstrip("/") + "/v1.0"
else:
    API_BASE = RAW_API_BASE.rstrip("/")
DEMO_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")


class ThreadsAPIError(RuntimeError):
    pass


@dataclass
class ThreadsPublishResult:
    creation_id: str
    thread_id: str


def _require_token(access_token: str | None = None) -> str:
    token = access_token or DEMO_ACCESS_TOKEN
    if not token:
        raise ThreadsAPIError("Нет access token для публикации. Подключите Threads-аккаунт.")
    return token


def _request(method: str, path: str, access_token: str | None = None, **params: Any) -> dict[str, Any]:
    token = _require_token(access_token)
    url = f"{API_BASE}{path}"
    payload = {"access_token": token, **params}
    response = requests.request(method, url, params=payload, timeout=30)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ThreadsAPIError(response.text) from exc
    return response.json()


def create_text_container(text: str, access_token: str | None = None) -> str:
    data = _request(
        "POST",
        "/me/threads",
        access_token=access_token,
        media_type="TEXT",
        text=text,
    )
    return data["id"]


def publish_container(creation_id: str, access_token: str | None = None) -> str:
    data = _request(
        "POST",
        "/me/threads_publish",
        access_token=access_token,
        creation_id=creation_id,
    )
    return data["id"]


def publish_text_post(text: str, access_token: str | None = None) -> ThreadsPublishResult:
    creation_id = create_text_container(text, access_token=access_token)
    thread_id = publish_container(creation_id, access_token=access_token)
    return ThreadsPublishResult(creation_id=creation_id, thread_id=thread_id)


def fetch_threads(access_token: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    data = _request(
        "GET",
        "/me/threads",
        access_token=access_token,
        limit=limit,
        fields="id,text,permalink,timestamp,username,media_type",
    )
    return data.get("data", [])


def fetch_thread_details(thread_id: str, access_token: str | None = None) -> dict[str, Any]:
    return _request(
        "GET",
        f"/{thread_id}",
        access_token=access_token,
        fields="id,text,permalink,timestamp,username,media_type",
    )


def fetch_thread_insights(thread_id: str, access_token: str | None = None) -> dict[str, Any]:
    data = _request(
        "GET",
        f"/{thread_id}/insights",
        access_token=access_token,
        metric="views,likes,replies,reposts,quotes",
    )
    metrics: dict[str, Any] = {}
    for item in data.get("data", []):
        name = item.get("name")
        values = item.get("values") or []
        if not name or not values:
            continue
        metrics[name] = values[0].get("value", 0)
    return metrics


def fetch_profile_insights(access_token: str | None = None) -> dict[str, Any]:
    data = _request(
        "GET",
        "/me/threads_insights",
        access_token=access_token,
        metric="views,likes,replies,reposts,quotes,clicks,followers_count",
    )
    metrics: dict[str, Any] = {}
    for item in data.get("data", []):
        name = item.get("name")
        values = item.get("values") or []
        if not name or not values:
            continue
        metrics[name] = values[0].get("value", 0)
    return metrics


def fetch_mentions(access_token: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    data = _request(
        "GET",
        "/me/mentions",
        access_token=access_token,
        limit=limit,
        fields="id,text,permalink,timestamp,username",
    )
    return data.get("data", [])


def fetch_replies(thread_id: str, access_token: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    data = _request(
        "GET",
        f"/{thread_id}/replies",
        access_token=access_token,
        limit=limit,
        fields="id,text,timestamp,username",
    )
    return data.get("data", [])


def delete_thread(thread_id: str, access_token: str | None = None) -> bool:
    _request("DELETE", f"/{thread_id}", access_token=access_token)
    return True


def keyword_search(
    query: str,
    access_token: str | None = None,
    limit: int = 20,
    search_type: str = "TOP",
    search_mode: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "q": query,
        "search_type": search_type,
        "limit": limit,
        "fields": "id,text,permalink,timestamp,username,topic_tag",
    }
    if search_mode:
        params["search_mode"] = search_mode
    data = _request(
        "GET",
        "/keyword_search",
        access_token=access_token,
        **params,
    )
    return data.get("data", [])


def profile_discovery(username: str, access_token: str | None = None) -> dict[str, Any]:
    return _request(
        "GET",
        "/profile_lookup",
        access_token=access_token,
        username=username,
    )


def profile_posts(username: str, access_token: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    data = _request(
        "GET",
        "/profile_posts",
        access_token=access_token,
        username=username,
        fields="id,text,permalink,timestamp,username,media_type,topic_tag",
        limit=limit,
    )
    return data.get("data", [])


def location_search(query: str, access_token: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    data = _request(
        "GET",
        "/location_search",
        access_token=access_token,
        q=query,
        fields="id,address,city,country,name,latitude,longitude,postal_code",
        limit=limit,
    )
    return data.get("data", [])


def hide_reply(reply_thread_id: str, access_token: str | None = None, hide: bool = True) -> dict[str, Any]:
    return _request(
        "POST",
        f"/{reply_thread_id}/manage_reply",
        access_token=access_token,
        hide=str(hide).lower(),
    )
