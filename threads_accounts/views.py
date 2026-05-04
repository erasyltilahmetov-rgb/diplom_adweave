import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ThreadsAccountForm
from .models import ThreadsAccount
from .oauth import ThreadsOAuthError, build_authorize_url, complete_oauth


OAUTH_STATE_SESSION_KEY = "threads_oauth_state"


@login_required
def account_edit(request, account_id: int):
    account = get_object_or_404(ThreadsAccount, pk=account_id, user=request.user)

    if request.method == "POST":
        form = ThreadsAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "Аккаунт обновлен.")
            return redirect("accounts")
    else:
        form = ThreadsAccountForm(instance=account)

    return render(request, "threads_accounts/account_edit.html", {"form": form, "account": account})


@login_required
def account_delete(request, account_id: int):
    account = get_object_or_404(ThreadsAccount, pk=account_id, user=request.user)
    if request.method == "POST":
        account.delete()
        messages.success(request, "Аккаунт удален.")
        return redirect("accounts")
    return render(request, "threads_accounts/account_delete.html", {"account": account})


@login_required
def oauth_start(request):
    state = secrets.token_urlsafe(24)
    request.session[OAUTH_STATE_SESSION_KEY] = state
    try:
        auth_url = build_authorize_url(state)
    except ThreadsOAuthError as exc:
        messages.error(request, f"OAuth не настроен: {exc}")
        messages.info(
            request,
            "Сделайте HTTPS-туннель (cloudflared tunnel --url http://127.0.0.1:8000), "
            "пропишите его в THREADS_REDIRECT_URI и добавьте этот же URL в Meta Developers.",
        )
        return redirect("accounts")
    return redirect(auth_url)


@login_required
def oauth_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, f"OAuth ошибка: {error}")
        return redirect("accounts")

    state = request.GET.get("state")
    expected_state = request.session.get(OAUTH_STATE_SESSION_KEY)
    if not state or not expected_state or state != expected_state:
        messages.error(request, "OAuth state не совпал. Попробуйте снова.")
        return redirect("accounts")
    request.session.pop(OAUTH_STATE_SESSION_KEY, None)

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Не получили code от Threads.")
        return redirect("accounts")

    try:
        result = complete_oauth(code)
    except ThreadsOAuthError as exc:
        messages.error(request, f"Не удалось подключить Threads: {exc}")
        return redirect("accounts")

    if not result.username:
        messages.error(request, "Не удалось получить username Threads.")
        return redirect("accounts")

    account, _created = ThreadsAccount.objects.update_or_create(
        user=request.user,
        username=result.username,
        defaults={
            "access_token": result.access_token,
            "token_expires_at": (
                timezone.now() + timedelta(seconds=result.expires_in)
                if result.expires_in
                else None
            ),
            "is_active": True,
        },
    )
    messages.success(request, f"Threads-аккаунт @{account.username} подключен.")
    return redirect("accounts")
