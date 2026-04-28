"""
Fakturoid Integration API

Endpoints:
  POST   /api/v1/integrations/fakturoid/test        – test the Fakturoid API connection
  POST   /api/v1/integrations/fakturoid/invoices    – create an invoice in Fakturoid

Credentials are stored per-firm in PluginConfig (plugin name: "fakturoid").
Use the generic plugin config API to save or remove credentials:
  PATCH  /api/v1/plugins/{firm_id}/plugin-configs/fakturoid/

Fakturoid API v2 docs: https://fakturoid.docs.apiary.io/
"""
from __future__ import annotations

import logging
from typing import List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import require_membership

logger = logging.getLogger(__name__)

fakturoid_router = Router(tags=["fakturoid"])
_auth = [django_auth]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@fakturoid_router.post(
    "/fakturoid/test",
    auth=_auth,
)
def test_fakturoid_connection(request):
    """
    Test the Fakturoid API connection by fetching account info.
    Credentials are read from the firm's Fakturoid plugin config.
    Returns the account name on success.
    """
    firm = getattr(request, "firm", None)
    require_membership(request, firm)

    from plugins.fakturoid import FakturoidPlugin
    return FakturoidPlugin.test_connection(str(firm.id))


@fakturoid_router.post(
    "/fakturoid/invoices",
    auth=_auth,
)
def create_fakturoid_invoice(request, payload: FakturoidInvoiceIn):
    """
    Create an invoice in Fakturoid from the provided line items.
    Credentials are read from the firm's Fakturoid plugin config.

    Either ``subject_id`` (Fakturoid internal ID) or ``subject_custom_id``
    (custom_id on the Subject record) must be provided to identify the customer.
    """
    firm = getattr(request, "firm", None)
    require_membership(request, firm)

    from plugins.fakturoid import FakturoidPlugin
    invoice_data = {
        "subject_id": payload.subject_id,
        "subject_custom_id": payload.subject_custom_id,
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
        "currency": payload.currency,
        "payment_method": payload.payment_method,
        "due": payload.due,
    }
    return FakturoidPlugin.create_invoice(str(firm.id), invoice_data)
