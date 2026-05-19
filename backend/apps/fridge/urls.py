from django.urls import path

from .views import (
    BarcodeLookupView,
    FridgeHistoryView,
    FridgeItemDetailsView,
    FridgeItemDetailView,
    FridgeListCreateView,
    ProductCategoryListView,
    ProductListView,
    ProductSearchView,
)

urlpatterns = [
    path("", FridgeListCreateView.as_view(), name="fridge-list"),
    path("<int:pk>/", FridgeItemDetailView.as_view(), name="fridge-item-detail"),
    path("<int:pk>/details/", FridgeItemDetailsView.as_view(), name="fridge-item-details"),
    path("scan/", BarcodeLookupView.as_view(), name="fridge-scan"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/search/", ProductSearchView.as_view(), name="product-search"),
    path("products/history/", FridgeHistoryView.as_view(), name="fridge-history"),
    path("categories/", ProductCategoryListView.as_view(), name="product-categories"),
]
