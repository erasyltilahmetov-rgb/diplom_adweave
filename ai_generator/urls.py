from django.urls import path
from . import views

app_name = "ai_generator"

urlpatterns = [
    path("rewrite/", views.rewrite_view, name="rewrite"),
    path("trending/", views.trending_view, name="trending"),
]
