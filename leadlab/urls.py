"""
URL configuration for leadlab project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve

from leadlab.api import api
from firms.superadmin_views import (
    superadmin_firms,
    superadmin_adjust_subscription,
    superadmin_impersonate,
    superadmin_stop_impersonation,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
    path("superadmin/firms/", superadmin_firms, name="superadmin-firms"),
    path("superadmin/firms/<str:firm_id>/adjust-subscription/", superadmin_adjust_subscription, name="superadmin-adjust-subscription"),
    path("superadmin/impersonate/<str:user_id>/", superadmin_impersonate, name="superadmin-impersonate"),
    path("superadmin/stop-impersonation/", superadmin_stop_impersonation, name="superadmin-stop-impersonation"),
    # Serve uploaded media files — works in both DEBUG and production.
    # In production with a reverse proxy (nginx), the proxy should intercept
    # /media/ before Django for better performance; this route is the fallback.
    path(
        "media/<path:path>",
        serve,
        {"document_root": settings.MEDIA_ROOT},
        name="media-serve",
    ),
    path("", include("frontend.urls")),
]

# In DEBUG also wire up via the helper (keeps dev behaviour unchanged).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
