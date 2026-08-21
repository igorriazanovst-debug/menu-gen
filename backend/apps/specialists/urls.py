from django.urls import path

from .views import (
    AssignmentAcceptView,
    CabinetClientExclusionsView,
    CabinetClientRationView,
    CabinetClientDayPlanView,
    CabinetClientSummaryView,
    CabinetClientTargetsHistoryView,
    CabinetClientWeightView,
    MyRecommendationDoneView,
    MyRecommendationsView,
    AssignmentEndView,
    AssignmentInviteView,
    CabinetClientListView,
    CabinetClientMenuDetailView,
    CabinetClientMenuListView,
    CabinetMenuItemSwapView,
    CabinetPendingAssignmentsView,
    CabinetRecommendationDetailView,
    CabinetRecommendationListView,
    MySpecialistsView,
    SpecialistInviteCodeView,
    SpecialistProfileView,
    SpecialistRegisterView,
)

urlpatterns = [
    # Профиль специалиста
    path("profile/", SpecialistProfileView.as_view(), name="specialist-profile"),
    path("register/", SpecialistRegisterView.as_view(), name="specialist-register"),
    # Назначения (пользователь → приглашает)
    path("invite/", AssignmentInviteView.as_view(), name="specialist-invite"),
    # MG_SPECINVITE: код приглашения специалиста и список «мои специалисты»
    path("invite-code/", SpecialistInviteCodeView.as_view(), name="specialist-invite-code"),
    path("my/", MySpecialistsView.as_view(), name="my-specialists"),
    path("assignments/<int:assignment_id>/accept/", AssignmentAcceptView.as_view(), name="assignment-accept"),
    path("assignments/<int:assignment_id>/end/", AssignmentEndView.as_view(), name="assignment-end"),
    # Кабинет специалиста
    path("cabinet/clients/", CabinetClientListView.as_view(), name="cabinet-clients"),
    path("cabinet/pending/", CabinetPendingAssignmentsView.as_view(), name="cabinet-pending"),
    # Меню клиента
    path("cabinet/clients/<int:family_id>/menus/", CabinetClientMenuListView.as_view(), name="cabinet-client-menus"),
    path(
        "cabinet/clients/<int:family_id>/menus/<int:menu_id>/",
        CabinetClientMenuDetailView.as_view(),
        name="cabinet-client-menu-detail",
    ),
    path(
        "cabinet/clients/<int:family_id>/menus/<int:menu_id>/items/<int:item_id>/",
        CabinetMenuItemSwapView.as_view(),
        name="cabinet-menu-item-swap",
    ),
    # MG_TRAINER: динамика клиента — сводка недели, вес, история целей
    path(
        "cabinet/clients/<int:family_id>/summary/",
        CabinetClientSummaryView.as_view(),
        name="cabinet-client-summary",
    ),
    path(
        "cabinet/clients/<int:family_id>/weight/",
        CabinetClientWeightView.as_view(),
        name="cabinet-client-weight",
    ),
    path(
        "cabinet/clients/<int:family_id>/targets-history/",
        CabinetClientTargetsHistoryView.as_view(),
        name="cabinet-client-targets-history",
    ),
    # MG_DIETITIAN: состав рациона и проверка исключений
    path(
        "cabinet/clients/<int:family_id>/ration/",
        CabinetClientRationView.as_view(),
        name="cabinet-client-ration",
    ),
    path(
        "cabinet/clients/<int:family_id>/exclusions/",
        CabinetClientExclusionsView.as_view(),
        name="cabinet-client-exclusions",
    ),
    # MG_COOK: наряд на день — что готовить, чего не хватает, что портится
    path(
        "cabinet/clients/<int:family_id>/day-plan/",
        CabinetClientDayPlanView.as_view(),
        name="cabinet-client-day-plan",
    ),
    # MG_TRAINER: рекомендации на стороне клиента
    path("recommendations/", MyRecommendationsView.as_view(), name="my-recommendations"),
    path(
        "recommendations/<int:rec_id>/done/",
        MyRecommendationDoneView.as_view(),
        name="my-recommendation-done",
    ),
    # Рекомендации
    path(
        "cabinet/clients/<int:family_id>/recommendations/",
        CabinetRecommendationListView.as_view(),
        name="cabinet-recommendations",
    ),
    path(
        "cabinet/clients/<int:family_id>/recommendations/<int:rec_id>/",
        CabinetRecommendationDetailView.as_view(),
        name="cabinet-recommendation-detail",
    ),
]
