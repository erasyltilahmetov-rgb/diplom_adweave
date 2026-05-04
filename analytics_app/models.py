from django.db import models


class PostAnalytics(models.Model):
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="analytics",
    )
    captured_at = models.DateTimeField("Снимок на", auto_now_add=True)
    impressions = models.PositiveIntegerField("Показы", default=0)
    likes = models.PositiveIntegerField("Лайки", default=0)
    replies = models.PositiveIntegerField("Ответы", default=0)
    reposts = models.PositiveIntegerField("Репосты", default=0)
    quotes = models.PositiveIntegerField("Цитирования", default=0)
    engagement_rate = models.DecimalField(
        "Engagement rate",
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Аналитика поста"
        verbose_name_plural = "Аналитика постов"

    def __str__(self) -> str:
        return f"Analytics for {self.post} ({self.captured_at:%Y-%m-%d})"


class ProfileAnalytics(models.Model):
    account = models.ForeignKey(
        "threads_accounts.ThreadsAccount",
        on_delete=models.CASCADE,
        related_name="profile_analytics",
    )
    captured_at = models.DateTimeField("Снимок на", auto_now_add=True)
    views = models.PositiveIntegerField("Просмотры профиля", default=0)
    followers = models.PositiveIntegerField("Подписчики", default=0)
    threads_count = models.PositiveIntegerField("Постов", default=0)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Аналитика профиля"
        verbose_name_plural = "Аналитика профилей"

    def __str__(self) -> str:
        return f"Profile analytics for {self.account} ({self.captured_at:%Y-%m-%d})"


class ThreadsMention(models.Model):
    account = models.ForeignKey(
        "threads_accounts.ThreadsAccount",
        on_delete=models.CASCADE,
        related_name="mentions",
    )
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.SET_NULL,
        related_name="mentions",
        null=True,
        blank=True,
    )
    remote_id = models.CharField(max_length=64)
    username = models.CharField(max_length=150, blank=True)
    text = models.TextField(blank=True)
    permalink = models.URLField(blank=True)
    created_at_remote = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Упоминание"
        verbose_name_plural = "Упоминания"
        unique_together = ("account", "remote_id")

    def __str__(self) -> str:
        return f"Mention @{self.username} ({self.remote_id})"


class ThreadsReply(models.Model):
    account = models.ForeignKey(
        "threads_accounts.ThreadsAccount",
        on_delete=models.CASCADE,
        related_name="replies",
    )
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        related_name="replies",
    )
    remote_id = models.CharField(max_length=64)
    username = models.CharField(max_length=150, blank=True)
    text = models.TextField(blank=True)
    created_at_remote = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-captured_at"]
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"
        unique_together = ("account", "remote_id")

    def __str__(self) -> str:
        return f"Reply @{self.username} ({self.remote_id})"
