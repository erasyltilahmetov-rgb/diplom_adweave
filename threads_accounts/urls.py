from django.urls import path

from .views import account_delete, account_edit, account_refresh_token, oauth_callback, oauth_start

app_name = "threads_accounts"

urlpatterns = [
    path("oauth/start/", oauth_start, name="oauth_start"),
    path("oauth/callback/", oauth_callback, name="oauth_callback"),
    path("<int:account_id>/edit/", account_edit, name="edit"),
    path("<int:account_id>/delete/", account_delete, name="delete"),
    path("<int:account_id>/refresh-token/", account_refresh_token, name="refresh_token"),
]
