from django.urls import path
from rest_framework.routers import DefaultRouter

from .media_upload import RecipeMediaUploadView  # UPLOAD_MEDIA_ROUTE
from .views import RecipeAuthorApplyView, RecipeCountryListView, RecipeViewSet

router = DefaultRouter()
router.register(r"", RecipeViewSet, basename="recipe")

urlpatterns = [
    path("upload-media/", RecipeMediaUploadView.as_view(), name="recipe-upload-media"),  # UPLOAD_MEDIA_ROUTE
    path("countries/", RecipeCountryListView.as_view(), name="recipe-countries"),
    path("authors/apply/", RecipeAuthorApplyView.as_view(), name="recipe-author-apply"),
] + router.urls
