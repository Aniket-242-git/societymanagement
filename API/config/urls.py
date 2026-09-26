"""Root URL configuration: versioned API + server-rendered UI."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # ---- REST API (versioned from day one) ----
    path("api/v1/auth/", include("API.apps.accounts.urls")),
    path("api/v1/", include("API.apps.flats.urls")),
    path("api/v1/", include("API.apps.announcements.urls")),
    path("api/v1/", include("API.apps.issues.urls")),
    path("api/v1/", include("API.apps.payments.urls")),
    path("api/v1/", include("API.apps.expenses.urls")),
    path("api/v1/", include("API.apps.reports.urls")),
    # ---- API docs (Swagger / OpenAPI) ----
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # ---- Server-rendered UI ----
    path("", include("UI.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
