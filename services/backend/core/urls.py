from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
    SpectacularJSONAPIView,
)

#=====================================================================
# Redirect to Docs Settings
#=====================================================================
def redirect_to_docs(request):
    """Redirect root URL to API documentation"""
    return redirect('swagger-ui')

api_v1_patterns = [
    path("", include("Apps.users.urls")),
    path("", include("Apps.profiles.urls")),
    path("", include("Apps.abilities.urls")),
    path("", include("Apps.journey.urls")),
    path("", include("Apps.learning.urls")),
    path("", include("Apps.progress.urls")),
    path("", include("Apps.notifications.urls")),
    path("", include("Apps.subscriptions.urls")),
    path("", include("Apps.support.urls")),
    path("", include("Apps.feedback.urls")),
    path("", include("Apps.legal.urls")),
    path("", include("Apps.resources.urls")),
]

class SwaggerJsonDownloadView(SpectacularJSONAPIView):
    """Serve OpenAPI schema in JSON format as an attachment so hitting the URL triggers a download."""

    def _get_schema_response(self, request):
        response = super()._get_schema_response(request)
        response["Content-Disposition"] = 'attachment; filename="swagger.json"'
        return response


urlpatterns = [
    # ---------------------------------------------------------------------------
    # Admin
    # ---------------------------------------------------------------------------
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "v1"))),
    # ---------------------------------------------------------------------------
    # API Documentation (drf-spectacular)
    # ---------------------------------------------------------------------------
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),                           # raw OpenAPI schema
    path("api/docs/",   SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),  # Swagger UI
    path("api/redoc/",  SpectacularRedocView.as_view(url_name="schema"),   name="redoc"),        # ReDoc
    path("api/swagger.json", SwaggerJsonDownloadView.as_view(), name="schema-json"),
    # ---------------------------------------------------------------------------
    # Root redirect
    # ---------------------------------------------------------------------------
    path('', redirect_to_docs, name='root-redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
