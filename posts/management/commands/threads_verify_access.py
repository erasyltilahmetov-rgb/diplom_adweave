from __future__ import annotations

import datetime as dt
import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from posts.threads_api import (
    ThreadsAPIError,
    create_text_container,
    delete_thread,
    fetch_mentions,
    fetch_profile_insights,
    fetch_replies,
    fetch_thread_insights,
    fetch_threads,
    hide_reply,
    keyword_search,
    location_search,
    profile_discovery,
    profile_posts,
    publish_container,
)
from threads_accounts.models import ThreadsAccount


class Command(BaseCommand):
    help = "Run one-time verification calls for Threads API permissions."

    def add_arguments(self, parser):
        parser.add_argument("--account-id", type=int, help="ThreadsAccount ID to use.")
        parser.add_argument("--token", type=str, help="Override access token.")
        parser.add_argument("--username", type=str, default="instagram", help="Username for profile discovery.")
        parser.add_argument("--keyword", type=str, default="marketing", help="Keyword for search.")
        parser.add_argument("--location", type=str, default="New York", help="Location query for tagging search.")
        parser.add_argument(
            "--no-delete",
            action="store_true",
            help="Do not delete the test post (skip threads_delete).",
        )

    def _resolve_token(self, options) -> str:
        if options.get("token"):
            return options["token"]
        account_id = options.get("account_id")
        if account_id:
            try:
                account = ThreadsAccount.objects.get(id=account_id)
            except ThreadsAccount.DoesNotExist as exc:
                raise CommandError(f"ThreadsAccount с id={account_id} не найден.") from exc
            if not account.access_token:
                raise CommandError("У выбранного аккаунта нет access_token.")
            return account.access_token
        env_token = os.getenv("THREADS_ACCESS_TOKEN")
        if not env_token:
            raise CommandError("Нет токена. Укажите --token или --account-id.")
        return env_token

    def handle(self, *args, **options):
        token = self._resolve_token(options)
        username = options["username"]
        keyword = options["keyword"]
        location_query = options["location"]
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.stdout.write(self.style.NOTICE("=== Threads API Verification Calls ==="))
        self.stdout.write(f"token: {'*' * 6}{token[-6:]}")
        self.stdout.write(f"username: {username} | keyword: {keyword} | location: {location_query}")

        results: list[tuple[str, str]] = []

        def run_step(name: str, func, *fargs, **fkwargs) -> Any:
            try:
                data = func(*fargs, **fkwargs)
            except ThreadsAPIError as exc:
                results.append((name, f"ERROR: {exc}"))
                return None
            results.append((name, "OK"))
            return data

        # threads_basic: fetch own threads
        run_step("threads_basic (fetch_threads)", fetch_threads, access_token=token, limit=1)

        # threads_content_publish: create + publish
        text = f"AdWeave verification post · {now}"
        creation_id = run_step("threads_content_publish (create container)", create_text_container, text, token)
        thread_id = None
        if creation_id:
            thread_id = run_step("threads_content_publish (publish)", publish_container, creation_id, token)

        # threads_read_replies: read replies on created thread (if any)
        replies = []
        if thread_id:
            replies = run_step("threads_read_replies (fetch replies)", fetch_replies, thread_id, token, 5) or []

        # threads_manage_replies: hide first reply if exists
        if replies:
            reply_id = replies[0].get("id")
            if reply_id:
                run_step("threads_manage_replies (hide reply)", hide_reply, reply_id, token, True)
            else:
                results.append(("threads_manage_replies (hide reply)", "SKIP: no reply id"))
        else:
            results.append(("threads_manage_replies (hide reply)", "SKIP: no replies"))

        # threads_manage_mentions
        run_step("threads_manage_mentions (mentions)", fetch_mentions, token, 5)

        # threads_manage_insights: profile + thread insights
        run_step("threads_manage_insights (profile)", fetch_profile_insights, token)
        if thread_id:
            run_step("threads_manage_insights (thread)", fetch_thread_insights, thread_id, token)

        # threads_keyword_search
        run_step("threads_keyword_search", keyword_search, keyword, token, 5)

        # threads_profile_discovery + profile_posts
        run_step("threads_profile_discovery (lookup)", profile_discovery, username, token)
        run_step("threads_profile_discovery (posts)", profile_posts, username, token, 5)

        # threads_location_tagging
        run_step("threads_location_tagging (location_search)", location_search, location_query, token, 5)

        # threads_delete: cleanup
        if thread_id and not options["no_delete"]:
            run_step("threads_delete (delete thread)", delete_thread, thread_id, token)
        elif thread_id:
            results.append(("threads_delete (delete thread)", "SKIP: --no-delete"))

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("=== Results ==="))
        for name, status in results:
            self.stdout.write(f"{name}: {status}")
