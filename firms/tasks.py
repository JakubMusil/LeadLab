"""
firms.tasks
===========
Celery tasks for the firms app.

- deliver_webhook: delivers a signed POST request to a webhook endpoint.
"""

import hashlib
import hmac
import json
import logging
import time

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_webhook(self, endpoint_id: str, event: str, payload: dict):
    """
    Deliver a signed POST request to a WebhookEndpoint.

    The request body is a JSON-serialised ``{"event": ..., "payload": ...}``
    object.  A HMAC-SHA256 signature over the raw body is sent in the
    ``X-LeadLab-Signature`` header as ``sha256=<hex_digest>``.

    Retries up to 3 times with a 30-second delay on transient HTTP errors.
    Delivery outcome is recorded in a ``WebhookDelivery`` log entry.
    """
    import requests

    from firms.models import WebhookDelivery, WebhookEndpoint

    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
    except WebhookEndpoint.DoesNotExist:
        logger.warning("deliver_webhook: endpoint %s not found; aborting.", endpoint_id)
        return

    if not endpoint.is_active:
        logger.info("deliver_webhook: endpoint %s is inactive; skipping.", endpoint_id)
        return

    body = json.dumps({"event": event, "payload": payload}, default=str).encode()
    signature = "sha256=" + hmac.new(
        endpoint.secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-LeadLab-Signature": signature,
        "X-LeadLab-Event": event,
        "User-Agent": "LeadLab-Webhook/1.7",
    }

    status_code = None
    response_body = ""
    error = ""
    success = False
    start = time.monotonic()

    try:
        resp = requests.post(
            endpoint.url,
            data=body,
            headers=headers,
            timeout=10,
        )
        status_code = resp.status_code
        response_body = resp.text[:2000]
        success = 200 <= resp.status_code < 300
        if not success:
            error = f"HTTP {resp.status_code}"
    except requests.RequestException as exc:
        error = str(exc)[:500]
        logger.warning("deliver_webhook: request to %s failed: %s", endpoint.url, exc)

    duration_ms = int((time.monotonic() - start) * 1000)

    WebhookDelivery.objects.create(
        endpoint=endpoint,
        event=event,
        payload=payload,
        status_code=status_code,
        response_body=response_body,
        error=error,
        duration_ms=duration_ms,
        success=success,
    )

    if not success and self.request.retries < self.max_retries:
        raise self.retry(countdown=30 * (2 ** self.request.retries))
