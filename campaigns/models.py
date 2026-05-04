from django.conf import settings
from django.db import models


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ACTIVE = "active", "Активна"
        PAUSED = "paused", "Пауза"
        COMPLETED = "completed", "Завершена"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaigns",
    )
    name = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    start_date = models.DateField("Старт", null=True, blank=True)
    end_date = models.DateField("Финиш", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Кампания"
        verbose_name_plural = "Кампании"

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    name = models.CharField("Название компании", max_length=255)
    contact_person = models.CharField("Контактное лицо", max_length=255)
    iin_bin = models.CharField("ИИН/БИН", max_length=12, unique=True)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=32, blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="companies",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Компания"
        verbose_name_plural = "Компании"

    def __str__(self) -> str:
        return self.name


class CompanyApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На рассмотрении"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"

    company_name = models.CharField("Название компании", max_length=255)
    contact_person = models.CharField("Контактное лицо", max_length=255)
    iin_bin = models.CharField("ИИН/БИН", max_length=12)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=32, blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    applicant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="company_applications",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_company_applications",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField("Рассмотрена", null=True, blank=True)
    approved_company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        related_name="application",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на компанию"
        verbose_name_plural = "Заявки на компании"

    def __str__(self) -> str:
        return f"{self.company_name} ({self.get_status_display()})"
