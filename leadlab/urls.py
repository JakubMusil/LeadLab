"""
URL configuration for leadlab project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

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
    path("", include("frontend.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
