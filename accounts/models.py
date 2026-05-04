from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Гость/Пользователь"
        ADMIN = "admin", "Админ"
        SUPPORT = "support", "Техподдержка"

    class Plan(models.TextChoices):
        BASIC = "basic", "Тариф обычный"
        STANDARD = "standard", "Тариф средний"
        PRO = "pro", "Тариф про"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.USER)
    plan = models.CharField("Тариф", max_length=20, choices=Plan.choices, default=Plan.BASIC)
    trial_started_at = models.DateTimeField("Старт пробного тарифа", null=True, blank=True)
    trial_ends_at = models.DateTimeField("Окончание пробного тарифа", null=True, blank=True)
    daily_limit_override = models.PositiveIntegerField("Лимит публикаций в день", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self) -> str:
        return f"{self.user} ({self.get_role_display()} · {self.get_plan_display()})"

    @property
    def trial_active(self) -> bool:
        if not self.trial_ends_at:
            return False
        return timezone.now() <= self.trial_ends_at

    @property
    def effective_plan(self) -> str:
        if self.plan == self.Plan.STANDARD and self.trial_ends_at and not self.trial_active:
            return self.Plan.BASIC
        if self.plan == self.Plan.PRO:
            return self.Plan.STANDARD
        return self.plan

    @property
    def daily_threads_limit(self) -> int:
        if self.daily_limit_override:
            return int(self.daily_limit_override)
        limits = {
            self.Plan.BASIC: 1,
            self.Plan.STANDARD: 10,
        }
        return limits.get(self.effective_plan, 1)

    @property
    def can_submit_company_application(self) -> bool:
        return self.effective_plan in {self.Plan.STANDARD} or self.role in {
            self.Role.ADMIN,
            self.Role.SUPPORT,
        }
