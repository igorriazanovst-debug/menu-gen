from django.urls import path

from .views import (
    BarcodeLookupView,
    FridgeExpiredBulkDeleteView,
    FridgeHistoryEntryView,
    FridgeHistoryView,
    FridgeItemConsumeView,
    FridgeItemDetailsView,
    FridgeItemDetailView,
    FridgeListCreateView,
    FridgeWriteOffUndoView,
    ProductCategoryListView,
    ProductDetailView,
    ProductListView,
    ProductSearchView,
    RecognizePhotoView,
)

urlpatterns = [
    path("", FridgeListCreateView.as_view(), name="fridge-list"),
    path("<int:pk>/", FridgeItemDetailView.as_view(), name="fridge-item-detail"),
    path("<int:pk>/details/", FridgeItemDetailsView.as_view(), name="fridge-item-details"),
    # MG_WRITEOFF: «израсходовал» — ручное списание позиции и отмена списания.
    path("<int:pk>/consume/", FridgeItemConsumeView.as_view(), name="fridge-item-consume"),
    path("write-offs/<int:pk>/", FridgeWriteOffUndoView.as_view(), name="fridge-write-off-undo"),
    path("scan/", BarcodeLookupView.as_view(), name="fridge-scan"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/search/", ProductSearchView.as_view(), name="product-search"),
    path("products/history/", FridgeHistoryView.as_view(), name="fridge-history"),
    path("products/history/<str:name>/", FridgeHistoryEntryView.as_view(), name="fridge-history-entry"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),  # MG_PRODOWN
    path("expired/delete/", FridgeExpiredBulkDeleteView.as_view(), name="fridge-expired-bulk-delete"),
    path("categories/", ProductCategoryListView.as_view(), name="product-categories"),
    path("recognize-photo/", RecognizePhotoView.as_view(), name="fridge-recognize-photo"),
]
