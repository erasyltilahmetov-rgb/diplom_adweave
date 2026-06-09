from django.urls import path
from . import views

app_name = "ai_generator"

urlpatterns = [
    path("rewrite/", views.rewrite_view, name="rewrite"),
    path("trending/", views.trending_view, name="trending"),
    path("live-scrape/", views.live_scrape_page, name="live_scrape"),
    path("live-scrape/stream/", views.live_scrape_stream, name="live_scrape_stream"),
    path("live-scrape/stop/", views.live_scrape_stop, name="live_scrape_stop"),
    path("live-scrape/save/", views.save_pack, name="save_pack"),
    path("packs/<int:pack_id>/", views.pack_detail, name="pack_detail"),
    path("packs/<int:pack_id>/optimize/", views.pack_optimize, name="pack_optimize"),
    path("competitor/", views.competitor_page, name="competitor"),
    path("competitor/stream/", views.competitor_stream, name="competitor_stream"),
    path("competitor/stop/", views.competitor_stop, name="competitor_stop"),
]
