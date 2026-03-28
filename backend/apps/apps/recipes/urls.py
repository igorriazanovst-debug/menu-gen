from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RecipeAuthorApplyView, RecipeViewSet

router = DefaultRouter()
router.register(r"", RecipeViewSet, basename="recipe")

urlpatterns = [
    path("author/apply/", RecipeAuthorApplyView.as_view(), name="recipe-author-apply"),
    path("", include(router.urls)),
]
