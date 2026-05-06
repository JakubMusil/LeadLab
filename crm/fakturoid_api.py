"""
Fakturoid Integration API

Endpoints:
  POST   /api/v1/integrations/fakturoid/test                    – test the Fakturoid API connection
  POST   /api/v1/integrations/fakturoid/invoices                – create an invoice in Fakturoid
  POST   /api/v1/integrations/fakturoid/from-proposal/{id}      – create invoice or quotation from a Proposal

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


class FakturoidFromProposalOut(Schema):
    ok: bool
    document_type: str = ""
    id: Optional[int] = None
    number: str = ""
    html_url: str = ""
    pdf_url: Optional[str] = None
    total: str = ""
    sent: bool = False
    error: Optional[str] = None


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


@fakturoid_router.post(
    "/fakturoid/from-proposal/{proposal_id}",
    auth=_auth,
    response={200: FakturoidFromProposalOut, 400: dict, 403: dict, 404: dict, 422: dict},
)
def create_from_proposal(request, proposal_id: str):
    """
    Create an invoice or quotation in Fakturoid from a LeadLab Proposal.

    The document type (invoice vs. quotation) and auto-send behaviour are
    controlled by the ``document_type`` and ``auto_send`` fields in the firm's
    Fakturoid plugin configuration.

    If ``auto_send`` is enabled the contact must have an e-mail address –
    otherwise the request is rejected with HTTP 422.

    A streamline activity (``invoice_sent``) is logged on the Proposal after
    a successful creation.
    """
    from crm.models import Activity, ActivityType, Proposal, ProposalItem
    from plugins.fakturoid import FakturoidPlugin

    firm = getattr(request, "firm", None)
    require_membership(request, firm)

    # Load the proposal
    try:
        proposal = (
            Proposal.objects
            .select_related("customer", "record__customer")
            .prefetch_related("items")
            .get(id=proposal_id, firm=firm)
        )
    except Proposal.DoesNotExist:
        return 404, {"detail": "Proposal not found."}

    # Load plugin config
    cfg = FakturoidPlugin.get_config(str(firm.id))
    if not cfg:
        return 400, {"detail": "Fakturoid plugin is not configured or disabled for this firm."}

    document_type = cfg.get("document_type", "invoice")
    auto_send = cfg.get("auto_send", False)

    # Resolve customer and email
    customer = None
    if proposal.record_id and proposal.record and proposal.record.customer_id:
        customer = proposal.record.customer
    elif proposal.customer_id:
        customer = proposal.customer

    if auto_send:
        customer_email = (customer.email or "").strip() if customer else ""
        if not customer_email:
            return 422, {
                "detail": (
                    "Auto-send is enabled but the contact has no e-mail address. "
                    "Please add an e-mail to the contact or disable auto-send in the Fakturoid plugin settings."
                )
            }

    # Build subject identifier for Fakturoid
    subject_custom_id = str(customer.id) if customer else None

    # Build line items from proposal items
    lines = []
    for item in sorted(proposal.items.all(), key=lambda i: (i.position, i.created_at)):
        unit_price_after_discount = float(item.unit_price) * (1 - float(item.discount) / 100)
        lines.append({
            "name": item.description,
            "quantity": float(item.quantity),
            "unit_name": "ks",
            "unit_price": f"{unit_price_after_discount:.2f}",
            "vat_rate": int(item.vat_rate),
        })

    doc_data = {
        "subject_custom_id": subject_custom_id,
        "note": proposal.notes or "",
        "lines": lines,
        "currency": proposal.currency or "CZK",
        "payment_method": "bank",
        "due": 14,
    }

    # Call the correct Fakturoid API method
    if document_type == "quotation":
        result = FakturoidPlugin.create_quotation(str(firm.id), doc_data, auto_send=auto_send)
        doc_key = "quotation"
    else:
        result = FakturoidPlugin.create_invoice(str(firm.id), doc_data, auto_send=auto_send)
        doc_key = "invoice"

    if not result.get("ok"):
        return 400, {"detail": result.get("error", "Unknown Fakturoid error.")}

    doc = result.get(doc_key, {})
    sent = result.get("sent", False)

    # Log activity on the proposal streamline
    Activity.objects.create(
        proposal=proposal,
        user=request.user,
        type=ActivityType.INVOICE_SENT,
        content_text=f"{doc.get('number', '')}",
        metadata={
            "invoice_id": str(doc.get("id", "")),
            "invoice_number": doc.get("number", ""),
            "url": doc.get("html_url", ""),
            "currency": proposal.currency or "CZK",
            "provider": "fakturoid",
            "document_type": document_type,
            "sent": sent,
        },
    )

    return 200, FakturoidFromProposalOut(
        ok=True,
        document_type=document_type,
        id=doc.get("id"),
        number=doc.get("number", ""),
        html_url=doc.get("html_url", ""),
        pdf_url=doc.get("pdf_url"),
        total=doc.get("total", ""),
        sent=sent,
    )
