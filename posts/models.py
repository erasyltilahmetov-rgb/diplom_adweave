from django.conf import settings
from django.db import models


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        READY = "ready", "Готово"
        PUBLISHED = "published", "Опубликовано"
        FAILED = "failed", "Ошибка"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="posts",
    )
    threads_account = models.ForeignKey(
        "threads_accounts.ThreadsAccount",
        on_delete=models.CASCADE,
        related_name="posts",
    )
    title = models.CharField("Заголовок", max_length=200, blank=True)
    content = models.TextField("Контент")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    ai_optimized = models.BooleanField("AI-оптимизация", default=False)
    published_at = models.DateTimeField("Опубликовано в", null=True, blank=True)
    threads_thread_id = models.CharField("Threads ID", max_length=64, blank=True)
    last_publish_error = models.TextField("Ошибка публикации", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Пост"
        verbose_name_plural = "Посты"

    def __str__(self) -> str:
        return self.title or f"Post #{self.pk}"


class PublishLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="publish_logs",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="publish_logs",
    )
    success = models.BooleanField("Успешно", default=False)
    thread_id = models.CharField("Threads ID", max_length=64, blank=True)
    error_message = models.TextField("Ошибка", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Лог публикации"
        verbose_name_plural = "Логи публикаций"

    def __str__(self) -> str:
        status = "OK" if self.success else "ERR"
        return f"{status} · {self.post} · {self.created_at:%Y-%m-%d %H:%M}"


class PostSchedule(models.Model):
    class ScheduleStatus(models.TextChoices):
        QUEUED = "queued", "В очереди"
        SCHEDULED = "scheduled", "Запланировано"
        CANCELLED = "cancelled", "Отменено"
        DONE = "done", "Выполнено"

    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name="schedule",
    )
    scheduled_for = models.DateTimeField("Запланировано на")
    status = models.CharField(
        "Статус расписания",
        max_length=20,
        choices=ScheduleStatus.choices,
        default=ScheduleStatus.SCHEDULED,
    )
    notes = models.CharField("Примечание", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_for"]
        verbose_name = "Расписание поста"
        verbose_name_plural = "Расписания постов"

    def __str__(self) -> str:
        return f"{self.post} @ {self.scheduled_for:%Y-%m-%d %H:%M}"
