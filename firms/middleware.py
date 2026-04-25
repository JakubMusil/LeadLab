"""
TenantMiddleware
================
Resolves and attaches the active ``Firm`` to every request so that downstream
views and API endpoints can enforce tenant isolation without repeating the
lookup logic.

Resolution order
----------------
1. ``X-Firm-ID`` HTTP header  (preferred for API clients)
2. ``firm_id`` query-string parameter  (fallback for simple GET requests)

If neither is present, ``request.firm`` is set to ``None`` (unauthenticated
or non-tenant routes such as ``/admin/`` should not require a Firm).

The middleware does **not** raise a permission error itself — that is the
responsibility of each view/endpoint via the ``require_membership`` helper or
the ``@active_subscription_required`` decorator defined in ``firms.auth``.
"""

import uuid

from django.http import JsonResponse

from firms.models import Firm, Membership


FIRM_HEADER = "HTTP_X_FIRM_ID"
FIRM_QUERY_PARAM = "firm_id"


class TenantMiddleware:
    """WSGI-compatible middleware that resolves the current tenant Firm."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.firm = self._resolve_firm(request)
        request.membership = self._resolve_membership(request)
        return self.get_response(request)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_firm(request) -> Firm | None:
        """Return the Firm instance for the current request, or None."""
        raw_id = (
            request.META.get(FIRM_HEADER)
            or request.GET.get(FIRM_QUERY_PARAM)
        )
        if not raw_id:
            return None
        try:
            firm_uuid = uuid.UUID(str(raw_id))
        except (ValueError, AttributeError):
            return None
        return Firm.objects.filter(id=firm_uuid, is_active=True).first()

    @staticmethod
    def _resolve_membership(request) -> Membership | None:
        """
        Return the Membership linking the authenticated user to ``request.firm``,
        or None if either is absent.
        """
        if not getattr(request, "firm", None):
            return None
        if not request.user or not request.user.is_authenticated:
            return None
        return (
            Membership.objects
            .select_related("user", "firm")
            .filter(user=request.user, firm=request.firm)
            .first()
        )
