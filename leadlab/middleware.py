"""
Custom middleware for LeadLab.
"""

from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """
    Adds a ``Content-Security-Policy`` response header to every response.

    The policy is assembled from individual ``CSP_*`` Django settings so that
    operators can override specific directives via environment variables without
    touching Python code.

    The middleware deliberately uses ``Content-Security-Policy`` (enforced)
    rather than ``Content-Security-Policy-Report-Only`` so that the policy is
    active in all environments.  Set ``CSP_REPORT_URI`` to send violation
    reports to an endpoint.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        directives = {
            "default-src": getattr(settings, "CSP_DEFAULT_SRC", "'self'"),
            "script-src": getattr(
                settings,
                "CSP_SCRIPT_SRC",
                "'self' 'unsafe-inline'",
            ),
            "style-src": getattr(
                settings,
                "CSP_STYLE_SRC",
                "'self' 'unsafe-inline'",
            ),
            "font-src": getattr(settings, "CSP_FONT_SRC", "'self'"),
            "img-src": getattr(settings, "CSP_IMG_SRC", "'self' data: blob:"),
            "connect-src": getattr(settings, "CSP_CONNECT_SRC", "'self'"),
            "worker-src": getattr(settings, "CSP_WORKER_SRC", "'self' blob:"),
            # media-src must explicitly allow blob: for voice memo playback
            # (MediaRecorder produces blob: URLs that <audio> needs to load).
            "media-src": getattr(settings, "CSP_MEDIA_SRC", "'self' blob:"),
        }

        report_uri = getattr(settings, "CSP_REPORT_URI", "")
        if report_uri:
            directives["report-uri"] = report_uri

        self._policy = "; ".join(
            f"{k} {v}" for k, v in directives.items() if v
        )

    def __call__(self, request):
        response = self.get_response(request)
        if self._policy and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self._policy
        return response
