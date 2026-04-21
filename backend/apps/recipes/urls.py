from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RecipeAuthorApplyView, RecipeViewSet
from .media_upload import RecipeMediaUploadView

router = DefaultRouter()
router.register(r"", RecipeViewSet, basename="recipe")

urlpatterns = [
    path("author/apply/", RecipeAuthorApplyView.as_view(), name="recipe-author-apply"),
    path("upload-media/", RecipeMediaUploadView.as_view(), name="recipe-media-upload"),
    path("", include(router.urls)),
]
