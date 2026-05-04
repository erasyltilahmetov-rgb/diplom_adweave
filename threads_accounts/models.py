from django.conf import settings
from django.db import models


class ThreadsAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="threads_accounts",
    )
    username = models.CharField("Username", max_length=150)
    access_token = models.CharField("Access token", max_length=512, blank=True)
    refresh_token = models.CharField("Refresh token", max_length=512, blank=True)
    token_expires_at = models.DateTimeField("Token expires at", null=True, blank=True)
    is_active = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Threads account"
        verbose_name_plural = "Threads accounts"
        unique_together = ("user", "username")

    def __str__(self) -> str:
        return f"{self.username} ({self.user})"
