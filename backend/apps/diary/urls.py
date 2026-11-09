from django.urls import path

from .views import (  # DIARY_COPY_V3
    ActivityTypeListView,
    BodyMeasurementView,
    DiaryCopyView,
    DiaryEntryDetailView,
    DiaryImportFromMenuView,
    DiaryListCreateView,
    DiaryStatsView,
    WaterLogView,
    WeightLogView,
    WorkoutLogDetailView,
    WorkoutLogView,
)

urlpatterns = [
    path("", DiaryListCreateView.as_view(), name="diary-list"),
    path("<int:pk>/", DiaryEntryDetailView.as_view(), name="diary-entry-detail"),
    path("stats/", DiaryStatsView.as_view(), name="diary-stats"),
    path("water/", WaterLogView.as_view(), name="diary-water"),
    # MG_TRAINER: вес по датам — история, а не одно число в профиле.
    path("weight/", WeightLogView.as_view(), name="diary-weight"),
    # MG_BODYSIZE: обхваты тела по датам — рядом с весом и по тем же правилам.
    path("measurements/", BodyMeasurementView.as_view(), name="diary-measurements"),
    # MG_WORKOUT: физнагрузки. Справочник отдельно от записей: он общий.
    path("activities/", ActivityTypeListView.as_view(), name="diary-activities"),
    path("workouts/", WorkoutLogView.as_view(), name="diary-workouts"),
    path("workouts/<int:pk>/", WorkoutLogDetailView.as_view(), name="diary-workout-detail"),
    path("copy/", DiaryCopyView.as_view(), name="diary-copy"),  # DIARY_COPY_V3
    # MG_605D_V_urls
    path("import-from-menu/", DiaryImportFromMenuView.as_view(), name="diary-import-from-menu"),
]
