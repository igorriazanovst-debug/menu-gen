from django.urls import path

from .views import (
    DeletedMenuListView,
    MenuArchiveView,
    MenuDeleteView,
    MenuDetailView,
    MenuGenerateView,
    MenuItemSwapView,
    MenuListView,
    MenuPurgeAllView,
    MenuPurgeView,
    MenuRestoreView,
    ShoppingItemToggleView,
    ShoppingListView,
)

urlpatterns = [
    path("", MenuListView.as_view(), name="menu-list"),
    path("generate/", MenuGenerateView.as_view(), name="menu-generate"),
    path("quarantine/", DeletedMenuListView.as_view(), name="menu-quarantine"),
    path("quarantine/purge-all/", MenuPurgeAllView.as_view(), name="menu-purge-all"),
    path("quarantine/<int:deleted_id>/restore/", MenuRestoreView.as_view(), name="menu-restore"),
    path("quarantine/<int:deleted_id>/purge/", MenuPurgeView.as_view(), name="menu-purge"),
    path("<int:pk>/", MenuDetailView.as_view(), name="menu-detail"),
    path("<int:menu_id>/delete/", MenuDeleteView.as_view(), name="menu-delete"),
    path("<int:menu_id>/archive/", MenuArchiveView.as_view(), name="menu-archive"),
    path("<int:menu_id>/items/<int:item_id>/", MenuItemSwapView.as_view(), name="menu-item-swap"),
    path("<int:menu_id>/shopping-list/", ShoppingListView.as_view(), name="menu-shopping-list"),
    path(
        "<int:menu_id>/shopping-list/items/<int:item_id>/toggle/",
        ShoppingItemToggleView.as_view(),
        name="shopping-item-toggle",
    ),
]
