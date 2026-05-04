from __future__ import annotations

import os

from django import forms

from .models import ThreadsAccount


DEMO_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")


class ThreadsAccountForm(forms.ModelForm):
    class Meta:
        model = ThreadsAccount
        fields = ["username", "access_token", "is_active"]
        labels = {
            "username": "Username",
            "access_token": "Access token",
            "is_active": "Активен",
        }
        widgets = {
            "access_token": forms.Textarea(attrs={"rows": 3, "placeholder": "Вставьте access token"}),
        }

    def clean_access_token(self):
        token = (self.cleaned_data.get("access_token") or "").strip()
        if token:
            return token
        if DEMO_ACCESS_TOKEN:
            return ""
        raise forms.ValidationError("Нужен access token. Добавьте его здесь или в .env для demo.")
