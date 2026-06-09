import base64
import json
import queue
import threading
import time
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .services import rewrite_for_threads
from .trending import get_trending_from_db, get_trending_live, extract_entities, detect_language, _extract_texts, _extract_posts_full

THREADS_DB_PATH = getattr(settings, "THREADS_DB_PATH", "")


@csrf_exempt
@require_POST
def rewrite_view(request):
    """POST /ai/rewrite/ — переписать текст в стиле Threads."""
    try:
        data = json.loads(request.body)
        raw_text = data.get("text", "").strip()
        language = data.get("language", "ru")

        if not raw_text:
            return JsonResponse({"error": "Текст не может быть пустым"}, status=400)
        if len(raw_text) > 2000:
            return JsonResponse({"error": "Текст слишком длинный (макс. 2000 символов)"}, status=400)

        result = rewrite_for_threads(raw_text, language)
        return JsonResponse({"result": result})

    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=503)
    except Exception as e:
        return JsonResponse({"error": f"Внутренняя ошибка: {e}"}, status=500)


@csrf_exempt
def trending_view(request):
    """
    GET /ai/trending/           — тренды из базы
    GET /ai/trending/?live=1    — тренды из живого Threads
    GET /ai/trending/?lang=ru   — фильтр по языку (ru/kz/en/all)
    """
    live = request.GET.get("live") == "1"
    lang_filter = request.GET.get("lang", "all")

    try:
        if live:
            topics = get_trending_live(top_n=40)
        else:
            topics = get_trending_from_db(hours=72, top_n=40)

        # Фильтр по языку
        if lang_filter != "all":
            topics = [t for t in topics if t.get("lang") == lang_filter]

        return JsonResponse({"topics": topics[:20], "live": live, "lang": lang_filter})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ─── Live scraper ─────────────────────────────────────────────────────────────

# cancel_flags[session_key] = threading.Event()
_cancel_flags: dict = {}


_SCRAPER_MSGS = {
    "ru": {
        "search": lambda q: f"Поиск по запросу: «{q}»...",
        "open": "Открываю Threads...",
        "wait": "Жду загрузки...",
        "scroll": lambda i, n, c: f"Скролл {i}/{n} · постов: {c}",
        "stopped": lambda i: f"Остановлено на скролле {i}.",
        "done": lambda c: f"Готово! Собрано {c} постов.",
    },
    "en": {
        "search": lambda q: f"Searching: «{q}»...",
        "open": "Opening Threads...",
        "wait": "Waiting for page...",
        "scroll": lambda i, n, c: f"Scroll {i}/{n} · posts: {c}",
        "stopped": lambda i: f"Stopped at scroll {i}.",
        "done": lambda c: f"Done! Collected {c} posts.",
    },
    "kz": {
        "search": lambda q: f"Іздеу: «{q}»...",
        "open": "Threads ашылуда...",
        "wait": "Жүктелуді күтемін...",
        "scroll": lambda i, n, c: f"Айналдыру {i}/{n} · жазба: {c}",
        "stopped": lambda i: f"{i}-айналдыруда тоқтатылды.",
        "done": lambda c: f"Дайын! Жиналды {c} жазба.",
    },
}


def _run_playwright_scraper(q: queue.Queue, stop_event: threading.Event,
                             max_scrolls: int = 60, search_query: str = "", lang: str = "ru",
                             max_posts: int = 30):
    """Playwright в отдельном потоке. stop_event.set() — мягкая остановка."""
    msgs = _SCRAPER_MSGS.get(lang, _SCRAPER_MSGS["ru"])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        q.put({"type": "error", "msg": "Playwright не установлен."})
        q.put(None)
        return

    import sqlite3

    profile_dir = str(Path(THREADS_DB_PATH).parent / "browser_profile") if THREADS_DB_PATH else "/tmp/adweave_profile"
    found_posts = []
    seen_texts: set = set()

    def send_screenshot(page):
        if stop_event.is_set():
            return
        try:
            png = page.screenshot(type="jpeg", quality=55, full_page=False)
            q.put({"type": "screenshot", "img": base64.b64encode(png).decode()})
        except Exception:
            pass

    def on_response(response):
        if stop_event.is_set():
            return
        if "graphql" not in response.url and "/api/" not in response.url:
            return
        try:
            data = response.json()
            posts = _extract_posts_full(data)
            for p in posts:
                if len(found_posts) >= max_posts:
                    break
                text = p["text"]
                if text not in seen_texts:
                    seen_texts.add(text)
                    found_posts.append(p)
                    p["entities"] = extract_entities(text)[:5]
                    p["lang"] = detect_language(text)
                    q.put({"type": "post", **p})
        except Exception:
            pass

    live_browser = None
    try:
        with sync_playwright() as p:
            live_browser = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            try:
                page = live_browser.new_page()
                page.on("response", on_response)

                if search_query:
                    url = f"https://www.threads.com/search?q={search_query}&serp_type=default"
                    q.put({"type": "log", "msg": msgs["search"](search_query)})
                else:
                    url = "https://www.threads.com"
                    q.put({"type": "log", "msg": msgs["open"]})

                page.goto(url, timeout=30000)
                send_screenshot(page)

                q.put({"type": "log", "msg": msgs["wait"]})
                try:
                    page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass

                # Проверка: сессия протухла
                if "login" in page.url or "/accounts/" in page.url:
                    send_screenshot(page)
                    q.put({"type": "error", "msg": "⚠️ Сессия Threads истекла. Зайди на threads.com и авторизуйся заново."})
                    q.put(None)
                    return

                # Проверка: поиск пуст (редирект на главную или нет результатов)
                if search_query and page.url.rstrip("/") == "https://www.threads.com":
                    send_screenshot(page)
                    q.put({"type": "log", "msg": f"По запросу «{search_query}» ничего не найдено."})
                    q.put(None)
                    return

                send_screenshot(page)

                stale = 0
                last_logged_count = 0
                try:
                    prev_height = page.evaluate("document.body.scrollHeight")
                except Exception:
                    prev_height = 0

                for i in range(max_scrolls):
                    if stop_event.is_set():
                        q.put({"type": "log", "msg": msgs["stopped"](i + 1)})
                        break
                    if len(found_posts) >= max_posts:
                        break
                    page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
                    page.wait_for_timeout(1000)
                    if i % 2 == 0:
                        send_screenshot(page)
                    try:
                        at_bottom = page.evaluate(
                            "(window.scrollY + window.innerHeight + 400) >= document.body.scrollHeight"
                        )
                        new_height = page.evaluate("document.body.scrollHeight")
                    except Exception:
                        at_bottom = False
                        new_height = prev_height
                    if at_bottom:
                        if new_height == prev_height:
                            stale += 1
                            if stale >= 5:
                                break
                        else:
                            stale = 0
                    else:
                        stale = 0
                    prev_height = new_height
                    # Логируем только когда появились новые посты
                    cur = len(found_posts)
                    if cur > last_logged_count:
                        last_logged_count = cur
                        q.put({"type": "log", "msg": msgs["scroll"](i + 1, max_posts, cur)})

                q.put({"type": "log", "msg": msgs["done"](len(found_posts))})

                # Сохраняем тексты в posts.db
                if found_posts and THREADS_DB_PATH and Path(THREADS_DB_PATH).exists():
                    try:
                        conn = sqlite3.connect(THREADS_DB_PATH)
                        conn.execute("CREATE TABLE IF NOT EXISTS posts (text TEXT UNIQUE, collected_at TEXT)")
                        for post in found_posts:
                            try:
                                conn.execute(
                                    "INSERT OR IGNORE INTO posts (text, collected_at) VALUES (?, datetime('now'))",
                                    (post["text"],)
                                )
                            except Exception:
                                pass
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass

            finally:
                try:
                    live_browser.close()
                except Exception:
                    pass

    except Exception as e:
        q.put({"type": "error", "msg": str(e)})
    finally:
        q.put(None)  # сигнал завершения


@csrf_exempt
@login_required
def pack_optimize(request, pack_id):
    """
    POST /ai/packs/<id>/optimize/
    Берёт топ-5 постов пака по лайкам как few-shot примеры и переписывает текст.
    Body: {"text": "...", "language": "ru"}
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        from .models import ScrapedPack
        from django.shortcuts import get_object_or_404
        pack = get_object_or_404(ScrapedPack, pk=pack_id, user=request.user)
        top_posts = list(
            pack.posts.order_by("-likes").values_list("text", flat=True)[:5]
        )

        data = json.loads(request.body)
        raw_text = data.get("text", "").strip()
        language = data.get("language", "ru")

        if not raw_text:
            return JsonResponse({"error": "Текст пустой"}, status=400)

        result = rewrite_for_threads(raw_text, language=language, custom_examples=top_posts)
        return JsonResponse({"result": result, "pack_name": pack.name, "examples_used": len(top_posts)})
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=503)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def live_scrape_page(request):
    from .models import ScrapedPack
    packs = ScrapedPack.objects.filter(user=request.user)[:10]
    return render(request, "ai_generator/live_scrape.html", {"packs": packs})


@csrf_exempt
@login_required
def save_pack(request):
    """POST — сохранить собранные посты как пак."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    try:
        data = json.loads(request.body)
        posts_data = data.get("posts", [])
        name = data.get("name", "").strip() or f"Пак от {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}"
        if not posts_data:
            return JsonResponse({"error": "Нет постов"}, status=400)

        from .models import ScrapedPack, ScrapedPost
        pack = ScrapedPack.objects.create(
            user=request.user,
            name=name,
            posts_count=len(posts_data),
        )
        ScrapedPost.objects.bulk_create([
            ScrapedPost(
                pack=pack,
                text=p.get("text", "")[:500],
                username=p.get("username", ""),
                likes=int(p.get("likes", 0) or 0),
                replies=int(p.get("replies", 0) or 0),
                reposts=int(p.get("reposts", 0) or 0),
                lang=p.get("lang", "ru"),
                entities=p.get("entities", []),
            )
            for p in posts_data
        ])
        return JsonResponse({"ok": True, "pack_id": pack.id, "name": pack.name, "count": pack.posts_count})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def pack_detail(request, pack_id):
    """Страница просмотра сохранённого пака."""
    from .models import ScrapedPack, ScrapedPost
    from django.shortcuts import get_object_or_404
    pack = get_object_or_404(ScrapedPack, pk=pack_id, user=request.user)
    posts = pack.posts.all()

    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "likes")
    lang = request.GET.get("lang", "all")
    min_likes = request.GET.get("min_likes", "")

    if q:
        posts = posts.filter(text__icontains=q)
    if lang != "all":
        posts = posts.filter(lang=lang)
    if min_likes.isdigit():
        posts = posts.filter(likes__gte=int(min_likes))
    if sort == "replies":
        posts = posts.order_by("-replies")
    elif sort == "reposts":
        posts = posts.order_by("-reposts")
    elif sort == "newest":
        posts = posts.order_by("id")
    else:
        posts = posts.order_by("-likes")

    return render(request, "ai_generator/pack_detail.html", {
        "pack": pack,
        "posts": posts[:100],
        "q": q, "sort": sort, "lang": lang, "min_likes": min_likes,
    })


@login_required
def live_scrape_stream(request):
    """SSE-поток: запускает Playwright, стримит скриншоты и посты."""
    max_posts = min(int(request.GET.get("max_posts", 30)), 500)
    search_query = request.GET.get("q", "").strip()
    lang = request.GET.get("lang", "ru")
    base_key = request.session.session_key or "anon"
    # Уникальный ключ на каждый запрос — несколько вкладок не убивают друг друга
    session_key = f"{base_key}_{int(time.time())}"

    stop_event = threading.Event()
    _cancel_flags[session_key] = stop_event
    # Останавливаем предыдущий запуск этой сессии (если был)
    for k in list(_cancel_flags.keys()):
        if k != session_key and k.startswith(base_key):
            _cancel_flags[k].set()

    def event_stream():
        q: queue.Queue = queue.Queue(maxsize=300)
        t = threading.Thread(
            target=_run_playwright_scraper,
            args=(q, stop_event, 60, search_query, lang, max_posts),
            daemon=True,
        )
        t.start()
        last_event_time = time.time()
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                    last_event_time = time.time()
                    if event is None:
                        yield 'data: {"type":"done"}\n\n'
                        break
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    # Keepalive — держим соединение живым пока скрапер работает
                    if time.time() - last_event_time > 60:
                        yield 'data: {"type":"error","msg":"Таймаут — нет активности 60 сек"}\n\n'
                        break
                    yield ': keepalive\n\n'
        finally:
            stop_event.set()
            _cancel_flags.pop(session_key, None)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
def live_scrape_stop(request):
    """POST — остановить текущий скрапер для этой сессии."""
    base_key = request.session.session_key or "anon"
    stopped = False
    for k in list(_cancel_flags.keys()):
        if k.startswith(base_key):
            _cancel_flags[k].set()
            stopped = True
    return JsonResponse({"ok": stopped})

# ─── Competitor analysis ──────────────────────────────────────────────────────

_competitor_flags: dict = {}


def _run_competitor_scraper(q: queue.Queue, stop_event: threading.Event,
                             username: str, max_scrolls: int = 60, max_posts: int = 30):
    """Скрапит профиль конкурента, собирает посты с метриками."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        q.put({"type": "error", "msg": "Playwright не установлен."})
        q.put(None)
        return

    profile_dir = str(Path(THREADS_DB_PATH).parent / "browser_profile") if THREADS_DB_PATH else "/tmp/adweave_profile"
    found_posts = []
    seen_texts: set = set()  # normalized text for dedup
    profile_info = {}

    def _norm(t: str) -> str:
        return " ".join(t.lower().split())

    def send_screenshot(page):
        if stop_event.is_set():
            return
        try:
            png = page.screenshot(type="jpeg", quality=55, full_page=False)
            q.put({"type": "screenshot", "img": base64.b64encode(png).decode()})
        except Exception:
            pass

    debug_sent = [False]

    target_user = username.lstrip("@").lower()

    def on_response(response):
        if stop_event.is_set():
            return
        if "graphql" not in response.url and "/api/" not in response.url:
            return
        try:
            data = response.json()
            _extract_profile_info(data, profile_info)
            posts = _extract_posts_full(data)
            for p in posts:
                if len(found_posts) >= max_posts:
                    break
                text = p["text"]
                # Только посты целевого профиля — игнорируем рекомендации
                post_user = (p.get("username") or "").lstrip("@").lower()
                if post_user and post_user != target_user:
                    continue
                norm = _norm(text)
                if text and norm not in seen_texts:
                    seen_texts.add(norm)
                    p["entities"] = extract_entities(text)[:5]
                    p["lang"] = detect_language(text)
                    found_posts.append(p)
                    if not debug_sent[0]:
                        debug_sent[0] = True
                        q.put({"type": "log", "msg": f"Метрики: ❤{p['likes']} 💬{p['replies']} 🔁{p['reposts']}"})
                    q.put({"type": "post", **p})
        except Exception:
            pass

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            try:
                page = browser.new_page()
                page.on("response", on_response)

                url = f"https://www.threads.com/@{username.lstrip('@')}"
                q.put({"type": "log", "msg": f"Открываю профиль @{username}..."})
                page.goto(url, timeout=30000)
                send_screenshot(page)

                try:
                    page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)

                # --- Проверка 1: сессия протухла (редирект на логин) ---
                current_url = page.url
                if "login" in current_url or "/accounts/" in current_url or "instagram.com" in current_url:
                    send_screenshot(page)
                    q.put({"type": "error", "msg": "⚠️ Сессия Threads истекла. Зайди на threads.com в браузере и авторизуйся заново."})
                    q.put(None)
                    return

                # --- Проверка 2: профиль не найден / приватный ---
                page_url_final = page.url
                try:
                    is_404 = page.evaluate("""() => {
                        const t = (document.body && document.body.innerText || '').toLowerCase();
                        return t.includes('not working or the page') ||
                               t.includes('page is gone') ||
                               t.includes('not all who wander') ||
                               t.includes('this page isn') ||
                               t.includes('страница не найдена');
                    }""")
                except Exception:
                    is_404 = False
                if is_404 or page_url_final.rstrip("/") == "https://www.threads.com":
                    send_screenshot(page)
                    q.put({"type": "error", "msg": f"Профиль @{username} не найден или приватный."})
                    q.put(None)
                    return

                # Перезагружаем чтобы Threads отдал посты через GraphQL (не HTML-рендер)
                q.put({"type": "log", "msg": "Перезагружаю для перехвата GraphQL..."})
                page.reload(timeout=30000)
                try:
                    page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass
                page.wait_for_timeout(2000)

                # --- Повторная проверка сессии после reload ---
                if "login" in page.url or "/accounts/" in page.url:
                    send_screenshot(page)
                    q.put({"type": "error", "msg": "⚠️ Сессия Threads истекла. Зайди на threads.com и авторизуйся заново."})
                    q.put(None)
                    return

                send_screenshot(page)
                q.put({"type": "log", "msg": "Профиль загружен. Читаю посты..."})

                def _dom_scrape():
                    """Собирает посты из DOM через pressable-контейнеры постов."""
                    try:
                        dom_texts = page.evaluate("""(targetUser) => {
                            const results = [];
                            const seen = new Set();

                            // Паттерны онбординга/UI — фильтруем
                            const UI_PATTERNS = [
                                /^finish\\b/i, /^introduce\\b/i, /^create(\\s+thread)?$/i,
                                /^say\\s+(what|your)/i, /^follow(\\s+\\d+\\s+profiles?)?$/i,
                                /^fill\\s+your/i, /^add(\\s+(profile|bio))?\\b/i,
                                /^make\\s+it\\s+easier/i, /^what[']?s\\s+new\\??$/i,
                                /^\\d+\\s+followers?$/i, /^opublikovать$/i,
                                /^(ветки|ответы|медиафайлы|репосты)$/i,
                                /^редактировать профиль$/i, /^для вас$/i,
                                /^закончите заполнение/i, /^добавьте биографию/i,
                                /^создайте ветку$/i, /^подпишитесь на/i,
                            ];

                            function isUI(text) {
                                const t = text.trim();
                                if (t.toLowerCase() === targetUser.toLowerCase()) return true;
                                return UI_PATTERNS.some(p => p.test(t));
                            }

                            function cleanText(raw) {
                                return raw
                                    .replace(/\\nTranslate(\\n|$)/g, '\\n')
                                    .replace(/\\nПеревод(\\n|$)/g, '\\n')
                                    .replace(/^(Translate|Перевод)\\n/g, '')
                                    .replace(/\\n(Translate|Перевод)$/g, '')
                                    .trim();
                            }

                            document.querySelectorAll('[data-pressable-container]').forEach(container => {
                                const dirEls = container.querySelectorAll('[dir="auto"]');
                                let best = '', bestLen = 0;
                                dirEls.forEach(el => {
                                    const t = (el.innerText || '').trim();
                                    if (t.length > bestLen) { bestLen = t.length; best = t; }
                                });
                                if (!best) return;
                                best = cleanText(best);
                                if (best.length < 2 || isUI(best)) return;
                                const norm = best.toLowerCase().replace(/\\s+/g, ' ');
                                if (!seen.has(norm)) {
                                    seen.add(norm);
                                    results.push(best);
                                }
                            });

                            return results;
                        }""", target_user)
                        added = 0
                        for text in dom_texts:
                            if len(found_posts) >= max_posts:
                                break
                            norm = _norm(text)
                            if norm in seen_texts:
                                continue
                            seen_texts.add(norm)
                            post = {"text": text, "username": username, "likes": 0, "replies": 0, "reposts": 0,
                                    "entities": extract_entities(text)[:5], "lang": detect_language(text)}
                            found_posts.append(post)
                            q.put({"type": "post", **post})
                            added += 1
                        return added
                    except Exception as e:
                        q.put({"type": "log", "msg": f"DOM ошибка: {e}"})
                        return 0

                # Скроллим — GraphQL ловит посты с метриками
                stale = 0
                last_logged_count = 0
                try:
                    prev_height = page.evaluate("document.body.scrollHeight")
                except Exception:
                    prev_height = 0

                for i in range(max_scrolls):
                    if stop_event.is_set():
                        q.put({"type": "log", "msg": f"Остановлено. Собрано: {len(found_posts)}"})
                        break
                    if len(found_posts) >= max_posts:
                        q.put({"type": "log", "msg": f"Цель достигнута: {len(found_posts)} постов."})
                        break
                    page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
                    page.wait_for_timeout(1000)
                    if i % 2 == 0:
                        send_screenshot(page)
                    try:
                        at_bottom = page.evaluate(
                            "(window.scrollY + window.innerHeight + 400) >= document.body.scrollHeight"
                        )
                        new_height = page.evaluate("document.body.scrollHeight")
                    except Exception:
                        at_bottom = False
                        new_height = prev_height
                    if at_bottom:
                        if new_height == prev_height:
                            stale += 1
                            if stale >= 5:
                                q.put({"type": "log", "msg": f"Конец ленты. GraphQL: {len(found_posts)} постов."})
                                break
                        else:
                            stale = 0
                    else:
                        stale = 0
                    prev_height = new_height
                    # Логируем только когда появились новые посты
                    cur = len(found_posts)
                    if cur > last_logged_count:
                        last_logged_count = cur
                        q.put({"type": "log", "msg": f"Собрано: {cur}/{max_posts} постов"})

                # DOM-скрапинг ПОСЛЕ цикла — подбираем SSR-посты без метрик
                added = _dom_scrape()
                if added:
                    q.put({"type": "log", "msg": f"DOM: +{added} постов (SSR, без метрик)"})

            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    except Exception as e:
        q.put({"type": "error", "msg": str(e)})
        q.put(None)
        return

    # Считаем статистику
    if found_posts:
        total_likes = sum(p.get("likes", 0) or 0 for p in found_posts)
        total_replies = sum(p.get("replies", 0) or 0 for p in found_posts)
        total_reposts = sum(p.get("reposts", 0) or 0 for p in found_posts)
        top_by_likes = sorted(found_posts, key=lambda x: x.get("likes", 0), reverse=True)[:5]
        top_by_replies = sorted(found_posts, key=lambda x: x.get("replies", 0), reverse=True)[:3]
        top_by_reposts = sorted(found_posts, key=lambda x: x.get("reposts", 0), reverse=True)[:3]
        avg_likes = round(total_likes / len(found_posts), 1)
        avg_replies = round(total_replies / len(found_posts), 1)

        q.put({"type": "stats", "data": {
            "total_posts": len(found_posts),
            "total_likes": total_likes,
            "total_replies": total_replies,
            "total_reposts": total_reposts,
            "avg_likes": avg_likes,
            "avg_replies": avg_replies,
            "top_by_likes": top_by_likes,
            "top_by_replies": top_by_replies,
            "top_by_reposts": top_by_reposts,
        }})
        q.put({"type": "log", "msg": f"Анализ завершён! {len(found_posts)} постов · avg ❤ {avg_likes}"})

    q.put(None)


def _extract_profile_info(obj, info: dict, depth=0):
    """Ищем данные профиля (followers, bio и т.д.) в GraphQL."""
    if depth > 8 or not isinstance(obj, dict):
        return
    for key in ("follower_count", "biography", "full_name", "username"):
        if key in obj and key not in info:
            info[key] = obj[key]
    for v in obj.values():
        if isinstance(v, (dict, list)):
            if isinstance(v, list):
                for item in v:
                    _extract_profile_info(item, info, depth + 1)
            else:
                _extract_profile_info(v, info, depth + 1)


@login_required
def competitor_page(request):
    return render(request, "ai_generator/competitor.html")


@login_required
def competitor_stream(request):
    username = request.GET.get("username", "").strip().lstrip("@")
    if not username:
        def err():
            yield 'data: {"type":"error","msg":"Укажи username"}\n\n'
        return StreamingHttpResponse(err(), content_type="text/event-stream")

    max_posts = min(int(request.GET.get("max_posts", 30)), 200)
    base_key = (request.session.session_key or "anon") + "_comp"
    session_key = f"{base_key}_{int(time.time())}"

    stop_event = threading.Event()
    _competitor_flags[session_key] = stop_event
    # Останавливаем предыдущий запуск если был
    for k in list(_competitor_flags.keys()):
        if k != session_key and k.startswith(base_key):
            _competitor_flags[k].set()

    def event_stream():
        q: queue.Queue = queue.Queue(maxsize=500)
        t = threading.Thread(
            target=_run_competitor_scraper,
            args=(q, stop_event, username, 120, max_posts),
            daemon=True,
        )
        t.start()
        last_event_time = time.time()
        try:
            while True:
                try:
                    event = q.get(timeout=15)
                    last_event_time = time.time()
                    if event is None:
                        yield 'data: {"type":"done"}\n\n'
                        break
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    if time.time() - last_event_time > 90:
                        yield 'data: {"type":"error","msg":"Таймаут — нет активности 90 сек"}\n\n'
                        break
                    yield ': keepalive\n\n'
        finally:
            stop_event.set()
            _competitor_flags.pop(session_key, None)

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@login_required
def competitor_stop(request):
    base_key = (request.session.session_key or "anon") + "_comp"
    stopped = False
    for k in list(_competitor_flags.keys()):
        if k.startswith(base_key):
            _competitor_flags[k].set()
            stopped = True
    return JsonResponse({"ok": stopped})
