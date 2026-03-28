from django.urls import path

from .views import BarcodeLookupView, FridgeItemDetailView, FridgeListCreateView, ProductSearchView

urlpatterns = [
    path("", FridgeListCreateView.as_view(), name="fridge-list"),
    path("<int:pk>/", FridgeItemDetailView.as_view(), name="fridge-item-detail"),
    path("scan/", BarcodeLookupView.as_view(), name="fridge-scan"),
    path("products/search/", ProductSearchView.as_view(), name="product-search"),
]
