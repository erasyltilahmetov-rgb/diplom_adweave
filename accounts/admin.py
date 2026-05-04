from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "role",
        "plan",
        "trial_started_at",
        "trial_ends_at",
        "daily_limit_override",
        "updated_at",
    )
    list_filter = ("role", "plan", "updated_at")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)
