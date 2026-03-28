from django.urls import path
from .views import DiaryListCreateView, DiaryEntryDetailView, DiaryStatsView, WaterLogView

urlpatterns = [
    path("", DiaryListCreateView.as_view(), name="diary-list"),
    path("<int:pk>/", DiaryEntryDetailView.as_view(), name="diary-entry-detail"),
    path("stats/", DiaryStatsView.as_view(), name="diary-stats"),
    path("water/", WaterLogView.as_view(), name="diary-water"),
]
