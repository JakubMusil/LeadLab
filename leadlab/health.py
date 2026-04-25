"""
Health check endpoint for LeadLab.

Returns HTTP 200 when all critical services are reachable, or HTTP 503
if any check fails.  Designed for use by load balancers and container
orchestration health probes.
"""
import logging

from django.core.cache import cache
from django.db import connection, OperationalError
from ninja import Router

logger = logging.getLogger(__name__)

health_router = Router(tags=["health"])


@health_router.get("/", auth=None, response={200: dict, 503: dict})
def health_check(request):
    """
    Probe database and cache connectivity.

    Returns::

        200 {"status": "ok", "checks": {"db": "ok", "cache": "ok"}}
        503 {"status": "error", "checks": {"db": "<error>", "cache": "<error>"}}
    """
    checks = {}
    ok = True

    # Database check
    try:
        connection.ensure_connection()
        checks["db"] = "ok"
    except OperationalError as exc:
        logger.error("health_check: database unreachable — %s", exc)
        checks["db"] = "error"
        ok = False

    # Cache / Redis check
    try:
        cache.set("health_check_probe", "1", timeout=5)
        if cache.get("health_check_probe") != "1":
            raise RuntimeError("Read-back mismatch")
        checks["cache"] = "ok"
    except Exception as exc:
        logger.error("health_check: cache unreachable — %s", exc)
        checks["cache"] = "error"
        ok = False

    status = "ok" if ok else "error"
    code = 200 if ok else 503
    return code, {"status": status, "checks": checks}
