from django.urls import path

from .views import (
    BarcodeLookupView,
    FridgeExpiredBulkDeleteView,
    FridgeHistoryEntryView,
    FridgeHistoryView,
    FridgeItemDetailsView,
    FridgeItemDetailView,
    FridgeListCreateView,
    ProductCategoryListView,
    ProductListView,
    ProductSearchView,
    RecognizePhotoView,
)

urlpatterns = [
    path("", FridgeListCreateView.as_view(), name="fridge-list"),
    path("<int:pk>/", FridgeItemDetailView.as_view(), name="fridge-item-detail"),
    path("<int:pk>/details/", FridgeItemDetailsView.as_view(), name="fridge-item-details"),
    path("scan/", BarcodeLookupView.as_view(), name="fridge-scan"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/search/", ProductSearchView.as_view(), name="product-search"),
    path("products/history/", FridgeHistoryView.as_view(), name="fridge-history"),
    path("products/history/<str:name>/", FridgeHistoryEntryView.as_view(), name="fridge-history-entry"),
    path("expired/delete/", FridgeExpiredBulkDeleteView.as_view(), name="fridge-expired-bulk-delete"),
    path("categories/", ProductCategoryListView.as_view(), name="product-categories"),
    path("recognize-photo/", RecognizePhotoView.as_view(), name="fridge-recognize-photo"),
]
