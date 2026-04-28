"""
Fakturoid Integration API (Phase 4.0)

Endpoints:
  GET    /api/v1/integrations/fakturoid/settings    – get current Fakturoid settings (masked)
  POST   /api/v1/integrations/fakturoid/settings    – save/update Fakturoid credentials
  DELETE /api/v1/integrations/fakturoid/settings    – remove Fakturoid credentials
  POST   /api/v1/integrations/fakturoid/test        – test the Fakturoid API connection
  POST   /api/v1/integrations/fakturoid/invoices    – create an invoice in Fakturoid

Fakturoid API v2 docs: https://fakturoid.docs.apiary.io/
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import requests as http_requests
from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import require_membership, PermissionDenied

logger = logging.getLogger(__name__)

fakturoid_router = Router(tags=["fakturoid"])
_auth = [django_auth]

FAKTUROID_API_BASE = "https://app.fakturoid.cz/api/v2/accounts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _firm(request):
    return getattr(request, "firm", None)


def _auth_header(email: str, token: str) -> Dict[str, str]:
    """Return HTTP Basic Auth header for Fakturoid API."""
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "User-Agent": "LeadLab (support@leadlab.io)",
        "Content-Type": "application/json",
    }


def _api_url(slug: str, path: str) -> str:
    return f"{FAKTUROID_API_BASE}/{slug}/{path}"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FakturoidSettingsIn(Schema):
    slug: str
    email: str
    token: str


class FakturoidSettingsOut(Schema):
    configured: bool
    slug: str
    email: str
    token_masked: str


class FakturoidInvoiceLineIn(Schema):
    name: str
    quantity: float = 1.0
    unit_name: str = "ks"
    unit_price: float
    vat_rate: int = 0


class FakturoidInvoiceIn(Schema):
    subject_id: Optional[int] = None
    subject_custom_id: Optional[str] = None
    note: str = ""
    lines: List[FakturoidInvoiceLineIn]
    currency: str = "CZK"
    payment_method: str = "bank"
    due: int = 14


class FakturoidInvoiceOut(Schema):
    id: int
    number: str
    html_url: str
    pdf_url: Optional[str] = None
    total: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@fakturoid_router.get(
    "/fakturoid/settings",
    response=FakturoidSettingsOut,
    auth=_auth,
)
def get_fakturoid_settings(request):
    """Return current Fakturoid credentials (token is masked)."""
    firm = _firm(request)
    require_membership(request, firm)

    configured = bool(firm.fakturoid_slug and firm.fakturoid_email and firm.fakturoid_token)
    token_masked = ""
    if firm.fakturoid_token:
        raw = firm.fakturoid_token
        token_masked = raw[:4] + "****" + raw[-4:] if len(raw) > 8 else "****"

    return FakturoidSettingsOut(
        configured=configured,
        slug=firm.fakturoid_slug or "",
        email=firm.fakturoid_email or "",
        token_masked=token_masked,
    )


@fakturoid_router.post(
    "/fakturoid/settings",
    auth=_auth,
)
def save_fakturoid_settings(request, payload: FakturoidSettingsIn):
    """Save Fakturoid API credentials for the active firm."""
    firm = _firm(request)
    membership = require_membership(request, firm)
    if not membership.is_admin_or_above:
        raise PermissionDenied("Only admin or owner can update Fakturoid settings.")

    firm.fakturoid_slug = payload.slug.strip()
    firm.fakturoid_email = payload.email.strip()
    firm.fakturoid_token = payload.token.strip()
    firm.save(update_fields=["fakturoid_slug", "fakturoid_email", "fakturoid_token"])

    return {"ok": True, "message": "Fakturoid settings saved."}


@fakturoid_router.delete(
    "/fakturoid/settings",
    auth=_auth,
)
def delete_fakturoid_settings(request):
    """Remove Fakturoid API credentials from the firm."""
    firm = _firm(request)
    membership = require_membership(request, firm)
    if not membership.is_admin_or_above:
        raise PermissionDenied("Only admin or owner can remove Fakturoid settings.")

    firm.fakturoid_slug = ""
    firm.fakturoid_email = ""
    firm.fakturoid_token = ""
    firm.save(update_fields=["fakturoid_slug", "fakturoid_email", "fakturoid_token"])

    return {"ok": True, "message": "Fakturoid credentials removed."}


@fakturoid_router.post(
    "/fakturoid/test",
    auth=_auth,
)
def test_fakturoid_connection(request):
    """
    Test the Fakturoid API connection by fetching account info.
    Returns the account name on success.
    """
    firm = _firm(request)
    require_membership(request, firm)

    if not (firm.fakturoid_slug and firm.fakturoid_email and firm.fakturoid_token):
        return {"ok": False, "error": "Fakturoid credentials not configured."}

    url = _api_url(firm.fakturoid_slug, "account.json")
    try:
        resp = http_requests.get(
            url,
            headers=_auth_header(firm.fakturoid_email, firm.fakturoid_token),
            timeout=10,
        )
    except Exception as exc:
        logger.error("Fakturoid test connection error: %s", exc)
        return {"ok": False, "error": "Network error — could not reach Fakturoid API."}

    if resp.status_code == 200:
        data = resp.json()
        return {"ok": True, "name": data.get("name", firm.fakturoid_slug)}
    elif resp.status_code == 401:
        return {"ok": False, "error": "Invalid Fakturoid credentials (401 Unauthorized)."}
    elif resp.status_code == 404:
        return {"ok": False, "error": f"Account '{firm.fakturoid_slug}' not found (404)."}
    else:
        return {"ok": False, "error": f"Fakturoid API returned HTTP {resp.status_code}."}


@fakturoid_router.post(
    "/fakturoid/invoices",
    auth=_auth,
)
def create_fakturoid_invoice(request, payload: FakturoidInvoiceIn):
    """
    Create an invoice in Fakturoid from the provided line items.

    Either ``subject_id`` (Fakturoid internal ID) or ``subject_custom_id``
    (custom_id on the Subject record) must be provided to identify the customer.
    """
    firm = _firm(request)
    require_membership(request, firm)

    if not (firm.fakturoid_slug and firm.fakturoid_email and firm.fakturoid_token):
        return {"ok": False, "error": "Fakturoid credentials not configured."}

    headers = _auth_header(firm.fakturoid_email, firm.fakturoid_token)

    # Resolve subject_id from custom_id if needed
    subject_id = payload.subject_id
    if not subject_id and payload.subject_custom_id:
        subjects_url = _api_url(firm.fakturoid_slug, "subjects.json")
        try:
            resp = http_requests.get(
                subjects_url,
                headers=headers,
                params={"custom_id": payload.subject_custom_id},
                timeout=10,
            )
            if resp.status_code == 200:
                subjects = resp.json()
                if subjects:
                    subject_id = subjects[0].get("id")
        except Exception as exc:
            logger.error("Fakturoid subject lookup error: %s", exc)
            return {"ok": False, "error": "Could not look up subject in Fakturoid."}

    invoice_data: Dict[str, Any] = {
        "currency": payload.currency,
        "payment_method": payload.payment_method,
        "due": payload.due,
        "note": payload.note,
        "lines": [
            {
                "name": line.name,
                "quantity": line.quantity,
                "unit_name": line.unit_name,
                "unit_price": f"{line.unit_price:.2f}",
                "vat_rate": line.vat_rate,
            }
            for line in payload.lines
        ],
    }
    if subject_id:
        invoice_data["subject_id"] = subject_id

    url = _api_url(firm.fakturoid_slug, "invoices.json")
    try:
        resp = http_requests.post(url, headers=headers, json=invoice_data, timeout=15)
    except Exception as exc:
        logger.error("Fakturoid create invoice error: %s", exc)
        return {"ok": False, "error": "Network error — could not reach Fakturoid API."}

    if resp.status_code in (201, 200):
        data = resp.json()
        return {
            "ok": True,
            "invoice": {
                "id": data.get("id"),
                "number": data.get("number", ""),
                "html_url": data.get("html_url", ""),
                "pdf_url": data.get("pdf_url"),
                "total": str(data.get("total", "")),
            },
        }
    else:
        try:
            err_body = resp.json()
            errors = err_body.get("errors", [resp.text])
        except Exception:
            errors = [resp.text]
        logger.error("Fakturoid invoice creation failed: %s %s", resp.status_code, errors)
        return {"ok": False, "error": f"Fakturoid returned HTTP {resp.status_code}: {errors}"}
