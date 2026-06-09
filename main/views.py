import os
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from accounts.models import UserProfile
from accounts.permissions import get_or_create_profile, get_role
from analytics_app.models import ProfileAnalytics, ThreadsMention, ThreadsReply, PostAnalytics
from campaigns.models import Campaign, Company
from posts.forms import ComposePostForm
from posts.models import Post, PostSchedule, PublishLog
from posts.threads_api import (
    ThreadsAPIError,
    delete_thread,
    fetch_mentions,
    fetch_profile_insights,
    fetch_replies,
    fetch_thread_details,
    fetch_threads,
    fetch_thread_insights,
    keyword_search,
    profile_discovery,
    publish_text_post,
)
from threads_accounts.forms import ThreadsAccountForm
from threads_accounts.models import ThreadsAccount

DEMO_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")


def home(request):
    return render(request, "main/home.html")


def features_page(request):
    return render(request, "main/features.html")


def pricing_page(request):
    profile = get_or_create_profile(request.user)
    if request.method == "POST" and request.user.is_authenticated:
        action = request.POST.get("action")
        if action == "start_trial":
            if not profile:
                messages.error(request, "Профиль пользователя не найден.")
            elif profile.trial_started_at:
                messages.warning(request, "Пробный период уже использован.")
            else:
                now = timezone.now()
                profile.plan = UserProfile.Plan.STANDARD
                profile.trial_started_at = now
                profile.trial_ends_at = now + timezone.timedelta(days=7)
                profile.save(update_fields=["plan", "trial_started_at", "trial_ends_at", "updated_at"])
                messages.success(request, "Пробный тариф «Средний» активирован на 7 дней.")
            return redirect("pricing")

    context = {
        "trial_active": bool(profile and profile.trial_active),
        "trial_ends_at": profile.trial_ends_at if profile else None,
        "trial_started_at": profile.trial_started_at if profile else None,
        "user_effective_plan": profile.effective_plan if profile else UserProfile.Plan.BASIC,
    }
    return render(request, "main/pricing.html", context)


def cases_page(request):
    return render(request, "main/cases.html")


def how_page(request):
    return render(request, "main/how.html")


def contacts_page(request):
    return render(request, "main/contacts.html")


def _publish_limit_state(user, profile, privileged: bool):
    today = timezone.localdate()
    published_today = PublishLog.objects.filter(
        user=user,
        success=True,
        created_at__date=today,
    ).count()
    daily_limit = profile.daily_threads_limit if profile else 0
    blocked = (published_today >= daily_limit) and not privileged
    remaining = max(daily_limit - published_today, 0)
    return published_today, daily_limit, remaining, blocked


def _account_token(account: ThreadsAccount) -> str | None:
    return account.access_token or DEMO_ACCESS_TOKEN


def _parse_remote_dt(value: str | None):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _extract_topics(items: list[dict]) -> list[tuple[str, int]]:
    stopwords = {
        "и", "в", "на", "о", "к", "по", "из", "за", "для", "что", "это", "как",
        "the", "and", "for", "with", "you", "your", "this", "that", "from", "are",
    }
    counts: dict[str, int] = {}
    for item in items:
        text = (item.get("text") or "").lower()
        if not text:
            continue
        for token in text.replace("\n", " ").split():
            token = token.strip(".,!?;:()[]{}<>\"'“”’")
            if not token or token in stopwords:
                continue
            if token.startswith("#") and len(token) > 1:
                key = token
            else:
                if len(token) < 4:
                    continue
                key = token
            counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:15]
    return top


def _normalize_keywords(raw: str) -> list[str]:
    if not raw:
        return []
    cleaned = raw.replace(",", "\n")
    keywords = [k.strip() for k in cleaned.splitlines() if k.strip()]
    return keywords[:20]


@login_required
def dashboard(request):
    user = request.user
    campaigns_qs = Campaign.objects.filter(user=user)
    posts_qs = Post.objects.filter(user=user).select_related("campaign", "threads_account")
    accounts_qs = ThreadsAccount.objects.filter(user=user, is_active=True)
    profile_analytics_qs = ProfileAnalytics.objects.filter(account__user=user).select_related("account")
    mentions_qs = ThreadsMention.objects.filter(account__user=user).select_related("account", "post")
    replies_qs = ThreadsReply.objects.filter(account__user=user).select_related("account", "post")

    status_counts = dict(
        campaigns_qs.values("status").annotate(total=Count("id")).values_list("status", "total")
    )

    scheduled_posts = (
        PostSchedule.objects.filter(post__user=user, status=PostSchedule.ScheduleStatus.SCHEDULED)
        .select_related("post", "post__campaign")
        .order_by("scheduled_for")[:5]
    )

    recent_posts = posts_qs.order_by("-created_at")[:5]
    latest_profile_analytics = profile_analytics_qs.order_by("-captured_at")[:3]
    latest_mentions = mentions_qs.order_by("-captured_at")[:5]
    latest_replies = replies_qs.order_by("-captured_at")[:5]

    context = {
        "stats": {
            "campaigns_total": campaigns_qs.count(),
            "campaigns_active": status_counts.get(Campaign.Status.ACTIVE, 0),
            "posts_total": posts_qs.count(),
            "accounts_total": accounts_qs.count(),
            "mentions_total": mentions_qs.count(),
            "replies_total": replies_qs.count(),
        },
        "scheduled_posts": scheduled_posts,
        "recent_posts": recent_posts,
        "latest_profile_analytics": latest_profile_analytics,
        "latest_mentions": latest_mentions,
        "latest_replies": latest_replies,
    }
    return render(request, "main/dashboard.html", context)


@login_required
def campaigns_page(request):
    campaigns = Campaign.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "main/campaigns.html", {"campaigns": campaigns})


@login_required
def posts_page(request):
    profile = get_or_create_profile(request.user)
    role = get_role(request.user)
    privileged = role in {UserProfile.Role.ADMIN, UserProfile.Role.SUPPORT} or request.user.is_superuser
    published_today, daily_limit, remaining_publishes, blocked = _publish_limit_state(
        request.user,
        profile,
        privileged,
    )

    posts = (
        Post.objects.filter(user=request.user)
        .select_related("campaign", "threads_account")
        .order_by("-created_at")
    )
    schedules = (
        PostSchedule.objects.filter(post__user=request.user)
        .select_related("post", "post__campaign")
        .order_by("scheduled_for")[:10]
    )
    context = {
        "posts": posts[:10],
        "schedules": schedules,
        "published_today": published_today,
        "daily_limit": daily_limit,
        "remaining_publishes": remaining_publishes,
        "publishing_blocked": blocked,
        "is_privileged": privileged,
    }
    return render(request, "main/posts.html", context)


@login_required
def compose_page(request):
    profile = get_or_create_profile(request.user)
    role = get_role(request.user)
    privileged = role in {UserProfile.Role.ADMIN, UserProfile.Role.SUPPORT} or request.user.is_superuser
    published_today, daily_limit, remaining_publishes, blocked = _publish_limit_state(
        request.user,
        profile,
        privileged,
    )
    campaigns_count = Campaign.objects.filter(user=request.user).count()
    accounts_count = ThreadsAccount.objects.filter(user=request.user, is_active=True).count()
    has_campaigns = campaigns_count > 0
    has_accounts = accounts_count > 0

    if request.method == "POST":
        if not has_campaigns:
            messages.error(request, "Сначала создайте кампанию.")
            return redirect("campaigns:create")
        if not has_accounts:
            messages.error(request, "Сначала подключите Threads-аккаунт.")
            return redirect("accounts")
        form = ComposePostForm(request.POST, user=request.user)
        if form.is_valid():
            publish_now = form.cleaned_data.get("publish_now")
            scheduled_for = form.cleaned_data.get("scheduled_for")

            if publish_now and blocked:
                messages.error(
                    request,
                    f"Достигнут дневной лимит публикаций ({daily_limit}). Повысите тариф.",
                )
                return redirect("pricing")

            post = form.save(commit=False)
            post.user = request.user
            post.save()
            form.save_m2m()

            if scheduled_for:
                PostSchedule.objects.update_or_create(
                    post=post,
                    defaults={
                        "scheduled_for": scheduled_for,
                        "status": PostSchedule.ScheduleStatus.SCHEDULED,
                    },
                )
                messages.success(request, "Пост сохранен и добавлен в расписание.")
                return redirect("posts")

            if publish_now:
                return _publish_post_with_feedback(request, post, privileged, daily_limit)

            messages.success(request, "Черновик поста сохранен.")
            return redirect("compose")
    else:
        form = ComposePostForm(user=request.user)

    context = {
        "form": form,
        "published_today": published_today,
        "daily_limit": daily_limit,
        "remaining_publishes": remaining_publishes,
        "publishing_blocked": blocked,
        "is_privileged": privileged,
        "has_campaigns": has_campaigns,
        "has_accounts": has_accounts,
    }
    return render(request, "main/compose.html", context)


@login_required
def history_page(request):
    posts = (
        Post.objects.filter(user=request.user)
        .select_related("campaign", "threads_account")
        .order_by("-created_at")
    )
    published_posts = posts.filter(status=Post.Status.PUBLISHED)[:20]
    failed_posts = posts.filter(status=Post.Status.FAILED)[:10]
    drafts = posts.filter(status__in=[Post.Status.DRAFT, Post.Status.READY])[:10]
    context = {
        "published_posts": published_posts,
        "failed_posts": failed_posts,
        "draft_posts": drafts,
    }
    return render(request, "main/history.html", context)


@login_required
def monitoring_page(request):
    accounts = ThreadsAccount.objects.filter(user=request.user, is_active=True).order_by("-created_at")
    mentions = ThreadsMention.objects.filter(account__user=request.user).select_related("account", "post")[:20]
    replies = ThreadsReply.objects.filter(account__user=request.user).select_related("account", "post")[:20]
    keyword_results: list[dict] = []
    trend_results: list[dict] = []
    trend_topics: list[tuple[str, int]] = []
    profile_result: dict | None = None
    threads_feed: list[dict] = []
    top_topics: list[tuple[str, int]] = []
    search_unavailable = False
    search_unavailable_message = ""
    query = ""
    profile_username = ""
    trend_keywords_raw = ""
    selected_account_id = None

    account = accounts.first()
    token = _account_token(account) if account else None

    if request.method == "POST":
        selected_account_id = request.POST.get("account_id") or None
        if selected_account_id and accounts.filter(id=selected_account_id).exists():
            account = accounts.get(id=selected_account_id)
            token = _account_token(account)

    def _mark_search_unavailable(exc: ThreadsAPIError) -> None:
        nonlocal search_unavailable, search_unavailable_message
        search_unavailable = True
        search_unavailable_message = (
            "Поиск и тренды недоступны для этого приложения. "
            "Нужны одобренные разрешения threads_keyword_search / threads_profile_discovery "
            "и статус приложения Live."
        )
        messages.warning(request, f"Мониторинг поиска ограничен: {exc}")

    def _is_search_unavailable(exc: ThreadsAPIError) -> bool:
        message = str(exc)
        return (
            "Unsupported get request" in message
            or "nonexisting field (search)" in message
            or "Object with ID 'search'" in message
        )

    if request.method == "POST" and token:
        query = (request.POST.get("keyword_query") or "").strip()
        profile_username = (request.POST.get("profile_username") or "").strip()
        action = request.POST.get("action")

        if action in {"fetch_threads", "top_topics"}:
            try:
                threads_feed = fetch_threads(access_token=token, limit=100)
                top_topics = _extract_topics(threads_feed)
            except ThreadsAPIError as exc:
                messages.error(request, f"Ошибка мониторинга Threads: {exc}")

        if action == "trend_scan":
            trend_keywords_raw = request.POST.get("trend_keywords", "")
            keywords = _normalize_keywords(trend_keywords_raw)
            combined: list[dict] = []
            try:
                for key in keywords:
                    combined.extend(keyword_search(key, access_token=token, limit=10))
                trend_results = combined[:50]
                trend_topics = _extract_topics(trend_results)
            except ThreadsAPIError as exc:
                if _is_search_unavailable(exc):
                    _mark_search_unavailable(exc)
                    try:
                        threads_feed = fetch_threads(access_token=token, limit=100)
                        trend_topics = _extract_topics(threads_feed)
                    except ThreadsAPIError:
                        pass
                else:
                    messages.error(request, f"Ошибка мониторинга Threads: {exc}")

        if query:
            try:
                keyword_results = keyword_search(query, access_token=token, limit=10)
            except ThreadsAPIError as exc:
                if _is_search_unavailable(exc):
                    _mark_search_unavailable(exc)
                else:
                    messages.error(request, f"Ошибка мониторинга Threads: {exc}")

        if profile_username:
            try:
                profile_result = profile_discovery(profile_username, access_token=token)
            except ThreadsAPIError as exc:
                if _is_search_unavailable(exc):
                    _mark_search_unavailable(exc)
                else:
                    messages.error(request, f"Ошибка мониторинга Threads: {exc}")

    context = {
        "accounts": accounts,
        "selected_account_id": int(selected_account_id) if selected_account_id else (account.id if account else None),
        "mentions": mentions,
        "replies": replies,
        "keyword_results": keyword_results,
        "profile_result": profile_result,
        "threads_feed": threads_feed,
        "top_topics": top_topics,
        "trend_results": trend_results,
        "trend_topics": trend_topics,
        "keyword_query": query,
        "profile_username": profile_username,
        "trend_keywords_raw": trend_keywords_raw,
        "monitoring_ready": bool(token),
        "search_unavailable": search_unavailable,
        "search_unavailable_message": search_unavailable_message,
    }
    return render(request, "main/monitoring.html", context)


@login_required
def permissions_page(request):
    scopes_raw = os.getenv("THREADS_SCOPES", "")
    configured_scopes = {s.strip() for s in scopes_raw.split(",") if s.strip()}
    permissions = [
        {
            "code": "threads_basic",
            "name": "Базовые данные профиля",
            "desc": "Просмотр собственных постов и данных профиля.",
            "feature": "История и публикации",
        },
        {
            "code": "threads_content_publish",
            "name": "Публикация",
            "desc": "Создание и публикация постов от имени профиля.",
            "feature": "Compose / публикация",
        },
        {
            "code": "threads_delete",
            "name": "Удаление постов",
            "desc": "Удаление опубликованных постов.",
            "feature": "История → удалить",
        },
        {
            "code": "threads_manage_insights",
            "name": "Аналитика",
            "desc": "Статистика профиля и постов.",
            "feature": "Дашборд / аналитика",
        },
        {
            "code": "threads_manage_mentions",
            "name": "Упоминания",
            "desc": "Получение постов, где вас упоминают.",
            "feature": "Мониторинг",
        },
        {
            "code": "threads_read_replies",
            "name": "Чтение ответов",
            "desc": "Чтение ответов на ваши посты.",
            "feature": "Мониторинг",
        },
        {
            "code": "threads_manage_replies",
            "name": "Управление ответами",
            "desc": "Ответы/модерация ответов на ветки.",
            "feature": "Мониторинг (дальше расширим)",
        },
        {
            "code": "threads_keyword_search",
            "name": "Поиск по ключевым словам",
            "desc": "Поиск контента по ключам.",
            "feature": "Мониторинг → поиск",
        },
        {
            "code": "threads_profile_discovery",
            "name": "Поиск профилей",
            "desc": "Поиск публичных профилей и постов.",
            "feature": "Мониторинг → поиск профиля",
        },
        {
            "code": "threads_location_tagging",
            "name": "Геометки",
            "desc": "Поиск локаций и публикация с геометкой.",
            "feature": "Будущая функция",
        },
    ]
    context = {
        "permissions": permissions,
        "configured_scopes": configured_scopes,
    }
    return render(request, "main/permissions.html", context)


@login_required
def accounts_page(request):
    accounts = ThreadsAccount.objects.filter(user=request.user).order_by("-created_at")
    redirect_uri = os.getenv("THREADS_REDIRECT_URI", "")
    tunnel_url = os.getenv("TUNNEL_URL", "")
    parsed_redirect = urlparse(redirect_uri) if redirect_uri else None
    oauth_ready = bool(
        redirect_uri
        and parsed_redirect
        and parsed_redirect.scheme == "https"
        and "xxxx.trycloudflare.com" not in redirect_uri
    )

    if request.method == "POST":
        form = ThreadsAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            messages.success(request, "Threads-аккаунт подключен.")
            return redirect("accounts")
    else:
        form = ThreadsAccountForm()

    context = {
        "accounts": accounts,
        "form": form,
        "oauth_ready": oauth_ready,
        "oauth_redirect_uri": redirect_uri,
        "tunnel_url": tunnel_url,
        "now": timezone.now(),
    }
    return render(request, "main/accounts.html", context)


@login_required
def analytics_page(request):
    top_campaigns = (
        Campaign.objects.filter(user=request.user)
        .annotate(posts_count=Count("posts"))
        .order_by("-posts_count", "-created_at")[:5]
    )
    return render(request, "main/analytics.html", {"top_campaigns": top_campaigns})


def privacy_page(request):
    return render(request, "main/privacy.html")


def terms_page(request):
    return render(request, "main/terms.html")


def about_page(request):
    return render(request, "main/about.html")


def updates_page(request):
    return render(request, "main/updates.html")


def help_page(request):
    return render(request, "main/help.html")


def careers_page(request):
    return render(request, "main/careers.html")


@login_required
def profile_page(request):
    user = request.user
    profile = get_or_create_profile(user)
    role = get_role(user)
    companies = Company.objects.filter(owner=user).order_by("-created_at")
    context = {
        "companies": companies,
        "is_admin": role == UserProfile.Role.ADMIN,
        "profile": profile,
    }
    return render(request, "main/profile.html", context)


@login_required
def publish_post(request, post_id: int):
    if request.method != "POST":
        return redirect("posts")

    post = get_object_or_404(
        Post.objects.select_related("user", "campaign", "threads_account"),
        pk=post_id,
    )

    profile = get_or_create_profile(request.user)
    role = get_role(request.user)
    privileged = role in {UserProfile.Role.ADMIN, UserProfile.Role.SUPPORT} or request.user.is_superuser

    if not privileged and post.user_id != request.user.id:
        messages.error(request, "Нельзя публиковать чужие посты.")
        return redirect("posts")

    published_today, daily_limit, _remaining, blocked = _publish_limit_state(
        request.user,
        profile,
        privileged,
    )

    if blocked:
        messages.error(
            request,
            f"Достигнут дневной лимит публикаций ({daily_limit}). Повысите тариф.",
        )
        return redirect("pricing")

    return _publish_post_with_feedback(request, post, privileged, daily_limit)


@login_required
def sync_threads_data(request):
    if request.method != "POST":
        return redirect("dashboard")

    accounts = ThreadsAccount.objects.filter(user=request.user, is_active=True).order_by("-created_at")
    if not accounts:
        messages.error(request, "Нет активных Threads-аккаунтов для синхронизации.")
        return redirect("accounts")

    insights_created = 0
    mentions_created = 0
    replies_created = 0
    profile_snapshots = 0

    for account in accounts:
        token = _account_token(account)
        if not token:
            messages.error(request, f"У аккаунта @{account.username} нет access token.")
            continue

        try:
            profile_metrics = fetch_profile_insights(access_token=token)
            ProfileAnalytics.objects.create(
                account=account,
                views=int(profile_metrics.get("views", 0) or 0),
                followers=int(profile_metrics.get("followers_count", 0) or 0),
                threads_count=int(profile_metrics.get("threads_count", 0) or 0),
                raw=profile_metrics,
            )
            profile_snapshots += 1
        except ThreadsAPIError as exc:
            messages.error(request, f"Не удалось получить insights профиля @{account.username}: {exc}")

        posts = Post.objects.filter(user=request.user, threads_account=account, threads_thread_id__gt="")

        for post in posts:
            try:
                metrics = fetch_thread_insights(post.threads_thread_id, access_token=token)
                impressions = int(metrics.get("views", 0) or 0)
                likes = int(metrics.get("likes", 0) or 0)
                replies = int(metrics.get("replies", 0) or 0)
                reposts = int(metrics.get("reposts", 0) or 0)
                quotes = int(metrics.get("quotes", 0) or 0)
                engagement_rate = 0
                if impressions:
                    engagement_rate = ((likes + replies + reposts + quotes) / impressions) * 100
                PostAnalytics.objects.create(
                    post=post,
                    impressions=impressions,
                    likes=likes,
                    replies=replies,
                    reposts=reposts,
                    quotes=quotes,
                    engagement_rate=round(engagement_rate, 2),
                )
                insights_created += 1
            except ThreadsAPIError as exc:
                post.last_publish_error = str(exc)[:1000]
                post.save(update_fields=["last_publish_error", "updated_at"])

            try:
                replies_payload = fetch_replies(post.threads_thread_id, access_token=token, limit=20)
                for item in replies_payload:
                    reply, created = ThreadsReply.objects.update_or_create(
                        account=account,
                        post=post,
                        remote_id=str(item.get("id")),
                        defaults={
                            "username": item.get("username", "") or "",
                            "text": item.get("text", "") or "",
                            "created_at_remote": _parse_remote_dt(item.get("timestamp")),
                            "raw": item,
                        },
                    )
                    if created:
                        replies_created += 1
            except ThreadsAPIError:
                pass

        try:
            mentions_payload = fetch_mentions(access_token=token, limit=20)
            posts_map = {p.threads_thread_id: p for p in posts}
            for item in mentions_payload:
                remote_id = str(item.get("id"))
                mention_post = posts_map.get(remote_id)
                mention, created = ThreadsMention.objects.update_or_create(
                    account=account,
                    remote_id=remote_id,
                    defaults={
                        "post": mention_post,
                        "username": item.get("username", "") or "",
                        "text": item.get("text", "") or "",
                        "permalink": item.get("permalink", "") or "",
                        "created_at_remote": _parse_remote_dt(item.get("timestamp")),
                        "raw": item,
                    },
                )
                if created:
                    mentions_created += 1
        except ThreadsAPIError as exc:
            messages.error(request, f"Не удалось загрузить упоминания @{account.username}: {exc}")

    messages.success(
        request,
        "Синхронизация завершена: "
        f"insights={insights_created}, mentions={mentions_created}, replies={replies_created}, profiles={profile_snapshots}.",
    )
    return redirect("dashboard")


@login_required
def delete_post_remote(request, post_id: int):
    if request.method != "POST":
        return redirect("history")

    post = get_object_or_404(Post, pk=post_id, user=request.user)
    if not post.threads_thread_id:
        messages.error(request, "У поста нет Threads ID для удаления.")
        return redirect("history")

    token = _account_token(post.threads_account)
    if not token:
        messages.error(request, "Нет access token для удаления.")
        return redirect("accounts")

    try:
        delete_thread(post.threads_thread_id, access_token=token)
        post.status = Post.Status.DRAFT
        post.threads_thread_id = ""
        post.published_at = None
        post.save(update_fields=["status", "threads_thread_id", "published_at", "updated_at"])
        messages.success(request, "Пост удален из Threads.")
    except ThreadsAPIError as exc:
        messages.error(request, f"Не удалось удалить пост: {exc}")
    return redirect("history")


def _publish_post_with_feedback(request, post: Post, privileged: bool, daily_limit: int):
    access_token = post.threads_account.access_token or DEMO_ACCESS_TOKEN
    if not access_token:
        messages.error(
            request,
            "У выбранного Threads-аккаунта нет access token. Добавьте его в админке.",
        )
        return redirect("accounts")
    try:
        result = publish_text_post(post.content, access_token=access_token)
    except ThreadsAPIError as exc:
        error_text = str(exc)[:1000]
        post.status = Post.Status.FAILED
        post.last_publish_error = error_text
        post.save(update_fields=["status", "last_publish_error", "updated_at"])
        PublishLog.objects.create(
            user=request.user,
            post=post,
            success=False,
            error_message=error_text,
        )
        if '"code":190' in error_text or "Session has expired" in error_text or "Error validating access token" in error_text:
            messages.error(
                request,
                "Токен Threads-аккаунта истёк. Зайдите в «Аккаунты» и переподключите аккаунт через OAuth.",
            )
            return redirect("accounts")
        messages.error(request, f"Ошибка публикации в Threads: {error_text}")
        return redirect("posts")

    post.status = Post.Status.PUBLISHED
    post.published_at = timezone.now()
    post.threads_thread_id = result.thread_id
    post.last_publish_error = ""
    try:
        details = fetch_thread_details(result.thread_id, access_token=access_token)
        post.threads_permalink = details.get("permalink", "")
    except ThreadsAPIError:
        post.threads_permalink = ""
    post.save(update_fields=["status", "published_at", "threads_thread_id", "threads_permalink", "last_publish_error", "updated_at"])

    PublishLog.objects.create(
        user=request.user,
        post=post,
        success=True,
        thread_id=result.thread_id,
    )

    messages.success(request, f"Пост опубликован. Threads ID: {result.thread_id}")
    return redirect("history")
