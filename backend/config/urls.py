from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.users.urls.auth")),
    path("api/v1/users/", include("apps.users.urls.users")),
    path("api/v1/recipes/", include("apps.recipes.urls")),
    path("api/v1/family/", include("apps.family.urls")),
    path("api/v1/fridge/", include("apps.fridge.urls")),
    path("api/v1/menu/", include("apps.menu.urls")),
    path("api/v1/diary/", include("apps.diary.urls")),
    path("api/v1/specialists/", include("apps.specialists.urls")),
    path("api/v1/subscriptions/", include("apps.subscriptions.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/social/", include("apps.social.urls")),
    path("api/v1/sync/", include("apps.sync.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
