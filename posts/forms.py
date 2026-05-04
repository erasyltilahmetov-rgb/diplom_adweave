from __future__ import annotations

import os

from django import forms
from django.utils import timezone

from campaigns.models import Campaign
from threads_accounts.models import ThreadsAccount

from .models import Post, PostSchedule


DEMO_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")


class ComposePostForm(forms.ModelForm):
    publish_now = forms.BooleanField(required=False, label="Опубликовать сразу")
    scheduled_for = forms.DateTimeField(
        required=False,
        label="Запланировать на",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )

    class Meta:
        model = Post
        fields = ["campaign", "threads_account", "title", "content"]
        labels = {
            "campaign": "Кампания",
            "threads_account": "Threads-аккаунт",
            "title": "Заголовок",
            "content": "Текст поста",
        }
        widgets = {
            "content": forms.Textarea(attrs={"rows": 8, "placeholder": "Напишите текст поста..."}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["campaign"].queryset = Campaign.objects.filter(user=user).order_by("-created_at")
            self.fields["threads_account"].queryset = ThreadsAccount.objects.filter(user=user, is_active=True).order_by(
                "-created_at"
            )
        self.fields["scheduled_for"].widget.is_localized = False

    def clean(self):
        cleaned = super().clean()
        publish_now = cleaned.get("publish_now")
        scheduled_for = cleaned.get("scheduled_for")
        threads_account: ThreadsAccount | None = cleaned.get("threads_account")

        if publish_now and scheduled_for:
            self.add_error("scheduled_for", "Выберите что-то одно: публикация сейчас или по расписанию.")

        if scheduled_for and scheduled_for < timezone.now():
            self.add_error("scheduled_for", "Дата планирования должна быть в будущем.")

        if threads_account and not threads_account.access_token and not DEMO_ACCESS_TOKEN:
            self.add_error(
                "threads_account",
                "У выбранного аккаунта нет access token. Добавьте его в админке.",
            )

        return cleaned

    def save(self, commit=True):
        scheduled_for = self.cleaned_data.get("scheduled_for")
        publish_now = self.cleaned_data.get("publish_now")
        post = super().save(commit=False)
        post.status = Post.Status.READY if (publish_now or scheduled_for) else Post.Status.DRAFT

        if commit:
            post.save()
            if scheduled_for:
                PostSchedule.objects.update_or_create(
                    post=post,
                    defaults={
                        "scheduled_for": scheduled_for,
                        "status": PostSchedule.ScheduleStatus.SCHEDULED,
                    },
                )
        return post
