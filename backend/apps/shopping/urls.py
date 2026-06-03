# MG_SHOP001_urls
from django.urls import path

from .views import (
    PurchaseHistoryView,
    ShoppingItemDetailView,
    ShoppingItemToggleView,
    ShoppingItemsView,
    ShoppingListAccessView,
    ShoppingListDetailView,
    ShoppingListExportView,
    ShoppingListsView,
)

urlpatterns = [
    path("lists/", ShoppingListsView.as_view(), name="shopping-lists"),
    path("lists/<int:list_id>/", ShoppingListDetailView.as_view(), name="shopping-list-detail"),
    path("lists/<int:list_id>/items/", ShoppingItemsView.as_view(), name="shopping-items"),
    path("lists/<int:list_id>/items/<int:item_id>/", ShoppingItemDetailView.as_view(), name="shopping-item-detail"),
    path("lists/<int:list_id>/items/<int:item_id>/toggle/", ShoppingItemToggleView.as_view(), name="shopping-item-toggle"),
    path("lists/<int:list_id>/access/", ShoppingListAccessView.as_view(), name="shopping-list-access"),
    path("lists/<int:list_id>/export/", ShoppingListExportView.as_view(), name="shopping-list-export"),
    path("history/", PurchaseHistoryView.as_view(), name="shopping-history"),
]
