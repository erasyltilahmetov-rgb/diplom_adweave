from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from accounts.permissions import can_manage_companies

from .models import Campaign, Company, CompanyApplication


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user", "status", "start_date", "end_date")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("name", "description", "user__username", "user__email")
    autocomplete_fields = ("user",)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "iin_bin", "contact_person", "email", "owner")
    search_fields = ("name", "iin_bin", "contact_person", "email")
    autocomplete_fields = ("owner",)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.is_staff

    def has_add_permission(self, request):
        return can_manage_companies(request.user)

    def has_change_permission(self, request, obj=None):
        return can_manage_companies(request.user)

    def has_delete_permission(self, request, obj=None):
        return can_manage_companies(request.user)

    def get_readonly_fields(self, request, obj=None):
        if can_manage_companies(request.user):
            return super().get_readonly_fields(request, obj)
        return (
            "name",
            "contact_person",
            "iin_bin",
            "email",
            "phone",
            "address",
            "owner",
            "created_at",
            "updated_at",
        )


@admin.action(description="Одобрить заявки и создать компании")
def approve_applications(modeladmin, request, queryset):
    approved_count = 0
    skipped_count = 0

    with transaction.atomic():
        for application in queryset.select_for_update():
            if application.status == CompanyApplication.Status.APPROVED and application.approved_company_id:
                skipped_count += 1
                continue

            company, _created = Company.objects.get_or_create(
                iin_bin=application.iin_bin,
                defaults={
                    "name": application.company_name,
                    "contact_person": application.contact_person,
                    "email": application.email,
                    "phone": application.phone,
                    "address": application.address,
                    "owner": application.applicant_user,
                },
            )

            if application.applicant_user and company.owner_id is None:
                company.owner = application.applicant_user
                company.save(update_fields=["owner", "updated_at"])

            application.status = CompanyApplication.Status.APPROVED
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.approved_company = company
            application.save(update_fields=["status", "reviewed_by", "reviewed_at", "approved_company", "updated_at"])
            approved_count += 1

    if approved_count:
        modeladmin.message_user(
            request,
            f"Одобрено заявок: {approved_count}.",
            level=messages.SUCCESS,
        )
    if skipped_count:
        modeladmin.message_user(
            request,
            f"Пропущено уже одобренных: {skipped_count}.",
            level=messages.WARNING,
        )


@admin.register(CompanyApplication)
class CompanyApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company_name",
        "iin_bin",
        "applicant_user",
        "contact_person",
        "email",
        "status",
        "approved_company",
        "created_at",
    )
    list_filter = ("status", "created_at", "reviewed_at")
    search_fields = ("company_name", "iin_bin", "contact_person", "email", "applicant_user__username")
    readonly_fields = (
        "status",
        "applicant_user",
        "reviewed_by",
        "reviewed_at",
        "approved_company",
        "created_at",
        "updated_at",
    )
    actions = (approve_applications,)
