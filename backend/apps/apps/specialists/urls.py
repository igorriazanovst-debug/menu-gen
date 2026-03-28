from django.urls import path

from .views import (
    AssignmentAcceptView,
    AssignmentEndView,
    AssignmentInviteView,
    CabinetClientListView,
    CabinetClientMenuDetailView,
    CabinetClientMenuListView,
    CabinetMenuItemSwapView,
    CabinetPendingAssignmentsView,
    CabinetRecommendationDetailView,
    CabinetRecommendationListView,
    SpecialistProfileView,
    SpecialistRegisterView,
)

urlpatterns = [
    # Профиль специалиста
    path("profile/", SpecialistProfileView.as_view(), name="specialist-profile"),
    path("register/", SpecialistRegisterView.as_view(), name="specialist-register"),
    # Назначения (пользователь → приглашает)
    path("invite/", AssignmentInviteView.as_view(), name="specialist-invite"),
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
