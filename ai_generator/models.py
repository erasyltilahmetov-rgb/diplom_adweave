from django.conf import settings
from django.db import models


class ScrapedPack(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scraped_packs",
    )
    name = models.CharField("Название пака", max_length=200)
    posts_count = models.PositiveIntegerField("Кол-во постов", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Scraped Pack"
        verbose_name_plural = "Scraped Packs"

    def __str__(self):
        return f"{self.name} ({self.posts_count} постов)"


class ScrapedPost(models.Model):
    pack = models.ForeignKey(
        ScrapedPack,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    text = models.TextField("Текст")
    username = models.CharField("Username", max_length=150, blank=True)
    likes = models.PositiveIntegerField("Лайки", default=0)
    replies = models.PositiveIntegerField("Комменты", default=0)
    reposts = models.PositiveIntegerField("Репосты", default=0)
    lang = models.CharField("Язык", max_length=8, default="ru")
    entities = models.JSONField("Сущности", default=list)

    class Meta:
        ordering = ["-likes"]
        verbose_name = "Scraped Post"
        verbose_name_plural = "Scraped Posts"

    def __str__(self):
        return f"@{self.username}: {self.text[:60]}"
