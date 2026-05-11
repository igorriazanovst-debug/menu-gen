from django.urls import path

from .views import (
    DiaryEntryDetailView,
    DiaryImportFromMenuView,
    DiaryListCreateView,
    DiaryStatsView,
    WaterLogView,
)

urlpatterns = [
    path("", DiaryListCreateView.as_view(), name="diary-list"),
    path("<int:pk>/", DiaryEntryDetailView.as_view(), name="diary-entry-detail"),
    path("stats/", DiaryStatsView.as_view(), name="diary-stats"),
    path("water/", WaterLogView.as_view(), name="diary-water"),
    # MG_605D_V_urls
    path("import-from-menu/", DiaryImportFromMenuView.as_view(), name="diary-import-from-menu"),
]
