from django.contrib import admin

from .models import Post, PostSchedule, PublishLog


class PostScheduleInline(admin.StackedInline):
    model = PostSchedule
    extra = 0


class PublishLogInline(admin.TabularInline):
    model = PublishLog
    extra = 0
    readonly_fields = ("success", "thread_id", "error_message", "created_at")
    can_delete = False
    show_change_link = False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "campaign",
        "threads_account",
        "status",
        "ai_optimized",
        "threads_thread_id",
        "published_at",
    )
    list_filter = ("status", "ai_optimized", "created_at", "published_at")
    search_fields = ("title", "content", "campaign__name", "threads_account__username", "threads_thread_id")
    autocomplete_fields = ("user", "campaign", "threads_account")
    readonly_fields = ("threads_thread_id", "last_publish_error", "published_at", "created_at", "updated_at")
    inlines = (PostScheduleInline, PublishLogInline)


@admin.register(PostSchedule)
class PostScheduleAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "scheduled_for", "status")
    list_filter = ("status", "scheduled_for")
    autocomplete_fields = ("post",)


@admin.register(PublishLog)
class PublishLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "user", "post", "success", "thread_id")
    list_filter = ("success", "created_at")
    search_fields = ("user__username", "post__title", "thread_id", "error_message")
    autocomplete_fields = ("user", "post")
    readonly_fields = ("created_at",)
