# MG_SHOP001_urls
from django.urls import path

from .views import PendingSharedListsView  # MG_SHAREACCEPT
from .views import SharedAccessRespondView  # MG_SHAREACCEPT
from .views import ShoppingAddToFridgeView  # MG_SHOP2FRIDGE
from .views import ShoppingCountsView  # MG_T09
from .views import (
    PurchaseHistoryView,
    RubricSearchView,
    ShoppingItemDetailView,
    ShoppingItemsView,
    ShoppingItemToggleView,
    ShoppingListAccessView,
    ShoppingListDetailView,
    ShoppingListExportView,
    ShoppingListsView,
)

urlpatterns = [
    path("counts/", ShoppingCountsView.as_view(), name="shopping-counts"),  # MG_T09
    path("lists/", ShoppingListsView.as_view(), name="shopping-lists"),
    path("lists/<int:list_id>/", ShoppingListDetailView.as_view(), name="shopping-list-detail"),
    path("lists/<int:list_id>/items/", ShoppingItemsView.as_view(), name="shopping-items"),
    path("lists/<int:list_id>/items/<int:item_id>/", ShoppingItemDetailView.as_view(), name="shopping-item-detail"),
    path(
        "lists/<int:list_id>/items/<int:item_id>/toggle/",
        ShoppingItemToggleView.as_view(),
        name="shopping-item-toggle",
    ),
    path(
        "lists/<int:list_id>/add-to-fridge/",
        ShoppingAddToFridgeView.as_view(),
        name="shopping-add-to-fridge",
    ),  # MG_SHOP2FRIDGE
    path("lists/<int:list_id>/access/", ShoppingListAccessView.as_view(), name="shopping-list-access"),
    path("lists/<int:list_id>/export/", ShoppingListExportView.as_view(), name="shopping-list-export"),
    path("history/", PurchaseHistoryView.as_view(), name="shopping-history"),
    # MG_RUBRIC002
    path("rubric/search/", RubricSearchView.as_view(), name="shopping-rubric-search"),
    # MG_SHAREACCEPT
    path("pending/", PendingSharedListsView.as_view(), name="shopping-pending"),
    path("lists/<int:list_id>/respond/", SharedAccessRespondView.as_view(), name="shopping-respond"),
]

# MG_RUBRICBROWSE
from . import views as _mg_browse_views  # noqa: E402

urlpatterns += [
    path(
        "rubric/categories/",
        _mg_browse_views.RubricCategoriesView.as_view(),
        name="shopping-rubric-categories",
    ),
    path(
        "rubric/browse/",
        _mg_browse_views.RubricBrowseView.as_view(),
        name="shopping-rubric-browse",
    ),
]
