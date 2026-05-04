from django.contrib import admin

from .models import PostAnalytics, ProfileAnalytics, ThreadsMention, ThreadsReply


@admin.register(PostAnalytics)
class PostAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "post",
        "captured_at",
        "impressions",
        "likes",
        "replies",
        "reposts",
        "quotes",
        "engagement_rate",
    )
    list_filter = ("captured_at",)
    autocomplete_fields = ("post",)


@admin.register(ProfileAnalytics)
class ProfileAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "captured_at", "views", "followers", "threads_count")
    list_filter = ("captured_at",)
    autocomplete_fields = ("account",)


@admin.register(ThreadsMention)
class ThreadsMentionAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "post", "username", "remote_id", "captured_at")
    list_filter = ("captured_at",)
    search_fields = ("username", "text", "remote_id")
    autocomplete_fields = ("account", "post")


@admin.register(ThreadsReply)
class ThreadsReplyAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "post", "username", "remote_id", "captured_at")
    list_filter = ("captured_at",)
    search_fields = ("username", "text", "remote_id")
    autocomplete_fields = ("account", "post")
