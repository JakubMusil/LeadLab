"""
Simple cache-based rate limiter for LeadLab API endpoints.

Usage:
    @rate_limit("login", limit=5, window=60)
    def login_view(request, payload):
        ...

Set RATELIMIT_ENABLE = False in settings to disable globally (useful in tests).

IP resolution:
    By default, REMOTE_ADDR is used (safe against X-Forwarded-For spoofing).
    If the app runs behind a trusted reverse proxy that sets a reliable
    client-IP header, set RATELIMIT_IP_META_KEY in Django settings to the
    META key name (e.g. "HTTP_X_REAL_IP") so each client gets its own bucket.
"""
import functools
import logging

from django.conf import settings
from django.core.cache import cache
from ninja.errors import HttpError

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    """Return the client IP to use as the rate-limit key.

    Uses ``settings.RATELIMIT_IP_META_KEY`` when explicitly configured
    (e.g. ``"HTTP_X_REAL_IP"`` set by a trusted reverse proxy).  Falls back
    to ``REMOTE_ADDR`` to prevent X-Forwarded-For spoofing.
    """
    meta_key = getattr(settings, "RATELIMIT_IP_META_KEY", "REMOTE_ADDR")
    value = request.META.get(meta_key, "")
    # Take the first value in case the header contains a comma-separated list.
    return value.split(",")[0].strip()


def rate_limit(key_prefix: str, limit: int = 10, window: int = 60):
    """
    Decorator that limits how many times a given endpoint can be called
    by the same IP address within *window* seconds.

    Uses Django's cache backend (Redis in production) for atomic counters.
    Returns HTTP 429 when the limit is exceeded.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not getattr(settings, "RATELIMIT_ENABLE", True):
                return func(request, *args, **kwargs)

            ip = _get_client_ip(request)
            cache_key = f"rl:{key_prefix}:{ip}"

            # cache.add sets the key only if it does not exist yet (atomic in Redis).
            cache.add(cache_key, 0, window)
            try:
                count = cache.incr(cache_key)
            except ValueError:
                # Backend doesn't support incr on this key; treat as first request.
                logger.debug("rate_limit: incr failed for key %s", cache_key)
                count = 1

            if count > limit:
                raise HttpError(429, "Too many requests. Please try again later.")

            return func(request, *args, **kwargs)

        return wrapper
    return decorator
