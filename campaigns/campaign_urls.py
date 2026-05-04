from django.urls import path

from .campaign_views import campaign_create, campaign_delete, campaign_edit, campaign_list

app_name = "campaigns"

urlpatterns = [
    path("", campaign_list, name="list"),
    path("create/", campaign_create, name="create"),
    path("<int:campaign_id>/edit/", campaign_edit, name="edit"),
    path("<int:campaign_id>/delete/", campaign_delete, name="delete"),
]
