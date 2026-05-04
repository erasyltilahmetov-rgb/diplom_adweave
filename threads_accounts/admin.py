from django.contrib import admin

from .models import ThreadsAccount


@admin.register(ThreadsAccount)
class ThreadsAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "user", "is_active", "has_token", "token_expires_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("username", "user__username", "user__email")
    autocomplete_fields = ("user",)

    @admin.display(boolean=True, description="Token")
    def has_token(self, obj: ThreadsAccount) -> bool:
        return bool(obj.access_token)
