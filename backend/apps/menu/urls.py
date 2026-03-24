from django.urls import path

from .views import (
    MenuGenerateView,
    MenuListView,
    MenuDetailView,
    MenuItemSwapView,
    MenuArchiveView,
    ShoppingListView,
    ShoppingItemToggleView,
)

urlpatterns = [
    path("", MenuListView.as_view(), name="menu-list"),
    path("generate/", MenuGenerateView.as_view(), name="menu-generate"),
    path("<int:pk>/", MenuDetailView.as_view(), name="menu-detail"),
    path("<int:menu_id>/archive/", MenuArchiveView.as_view(), name="menu-archive"),
    path("<int:menu_id>/items/<int:item_id>/", MenuItemSwapView.as_view(), name="menu-item-swap"),
    path("<int:menu_id>/shopping-list/", ShoppingListView.as_view(), name="menu-shopping-list"),
    path("<int:menu_id>/shopping-list/items/<int:item_id>/toggle/",
         ShoppingItemToggleView.as_view(), name="shopping-item-toggle"),
]
