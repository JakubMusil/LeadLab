"""
Django Ninja API router – Proposals & Quote Builder (v2.3)

Public (no-auth) endpoints:
    GET  /crm/public/proposals/{token}              – read-only HTML view data
    POST /crm/public/proposals/{token}/respond      – accept or reject

Authenticated endpoints:
    GET  /crm/records/{record_id}/proposals             – list proposals on a record
    POST /crm/records/{record_id}/proposals             – create proposal
    GET  /crm/proposals/{id}                        – get proposal
    PUT  /crm/proposals/{id}                        – update proposal
    DELETE /crm/proposals/{id}                      – delete proposal
    POST /crm/proposals/{id}/apply-template         – apply a ProposalTemplate
    POST /crm/proposals/{id}/send                   – mark as Sent + generate public link
    GET  /crm/proposals/{id}/pdf                    – download PDF

    GET  /crm/proposals/{id}/items                  – list items
    POST /crm/proposals/{id}/items                  – create item
    PUT  /crm/proposals/{id}/items/{item_id}        – update item
    DELETE /crm/proposals/{id}/items/{item_id}      – delete item
    POST /crm/proposals/{id}/items/reorder          – update positions

    GET  /crm/proposal-templates                    – list templates
    POST /crm/proposal-templates                    – create template
    GET  /crm/proposal-templates/{id}               – get template
    PUT  /crm/proposal-templates/{id}               – update template
    DELETE /crm/proposal-templates/{id}             – delete template
    GET  /crm/proposal-templates/{id}/items         – list template items
    POST /crm/proposal-templates/{id}/items         – create template item
    PUT  /crm/proposal-templates/{id}/items/{iid}   – update template item
    DELETE /crm/proposal-templates/{id}/items/{iid} – delete template item

    GET  /crm/reports/proposal-analytics            – analytics
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone as tz
from ninja import Router, Schema
from ninja.security import django_auth

from crm.models import (
    Activity,
    ActivityType,
    Customer,
    FirmProposalItem,
    PipelineRecord,
    Proposal,
    ProposalItem,
    ProposalStatus,
    ProposalTemplate,
    ProposalTemplateItem,
)
from crm.soft_delete import perform_soft_delete
from firms.auth import (
    MembershipRole,
    PermissionDenied,
    require_membership,
)
from crm.api import _activity_out as _shared_activity_out

proposals_router = Router(tags=["proposals"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ErrorOut(Schema):
    detail: str


class ProposalItemOut(Schema):
    id: str
    proposal_id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    vat_rate: Decimal
    position: int
    subtotal: Decimal
    discount_amount: Decimal
    after_discount: Decimal
    tax: Decimal
    total: Decimal
    created_at: datetime


class ProposalItemIn(Schema):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    position: int = 0


class ProposalOut(Schema):
    id: str
    lead_id: Optional[str]
    customer_id: Optional[str]
    firm_id: str
    title: str
    status: str
    expiry_date: Optional[str]
    currency: str
    notes: str
    intro_text: str
    closing_text: str
    public_token: str
    token_expires_at: Optional[datetime]
    view_count: int
    first_viewed_at: Optional[datetime]
    sent_at: Optional[datetime]
    responded_at: Optional[datetime]
    total_value: Decimal
    items: List[ProposalItemOut]
    created_at: datetime
    updated_at: datetime


class ProposalIn(Schema):
    title: str
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    status: str = ProposalStatus.DRAFT
    expiry_date: Optional[str] = None
    currency: str = "CZK"
    notes: str = ""
    intro_text: str = ""
    closing_text: str = ""


class ProposalUpdateIn(Schema):
    title: Optional[str] = None
    status: Optional[str] = None
    expiry_date: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    intro_text: Optional[str] = None
    closing_text: Optional[str] = None


class ItemReorderIn(Schema):
    # list of {id: str, position: int}
    items: List[Dict]


class ApplyTemplateIn(Schema):
    template_id: str


class ProposalTemplateItemOut(Schema):
    id: str
    template_id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    vat_rate: Decimal
    position: int


class ProposalTemplateOut(Schema):
    id: str
    firm_id: str
    name: str
    intro_text: str
    closing_text: str
    items: List[ProposalTemplateItemOut]
    created_at: datetime
    updated_at: datetime


class ProposalTemplateIn(Schema):
    name: str
    intro_text: str = ""
    closing_text: str = ""


class ProposalTemplateItemIn(Schema):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    position: int = 0


class PublicProposalRespondIn(Schema):
    action: str  # "accept" or "reject"


class PublicProposalOut(Schema):
    id: str
    title: str
    status: str
    expiry_date: Optional[str]
    currency: str
    notes: str
    intro_text: str
    closing_text: str
    total_value: Decimal
    items: List[ProposalItemOut]
    firm_name: str
    firm_logo_url: Optional[str]
    firm_primary_color: str
    is_expired: bool


class ProposalAnalyticsOut(Schema):
    total: int
    draft: int
    sent: int
    viewed: int
    accepted: int
    rejected: int
    expired: int
    acceptance_rate: float
    rejection_rate: float
    avg_time_to_open_hours: Optional[float]
    template_stats: List[Dict]


class FirmProposalItemOut(Schema):
    id: str
    firm_id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    vat_rate: Decimal
    position: int
    sku: str = ''
    notes: str = ''
    image_url: str = ''
    created_at: datetime
    updated_at: datetime


class FirmProposalItemIn(Schema):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    position: int = 0
    sku: str = ''
    notes: str = ''
    image_url: str = ''


class AddFromCatalogIn(Schema):
    item_ids: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PUBLIC_LINK_TTL_DAYS = 30

def _item_out(item: ProposalItem) -> dict:
    return {
        "id": str(item.id),
        "proposal_id": str(item.proposal_id),
        "description": item.description,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "discount": item.discount,
        "vat_rate": item.vat_rate,
        "position": item.position,
        "subtotal": item.subtotal,
        "discount_amount": item.discount_amount,
        "after_discount": item.after_discount,
        "tax": item.tax,
        "total": item.total,
        "created_at": item.created_at,
    }


def _proposal_out(proposal: Proposal) -> dict:
    items = list(proposal.items.all())
    return {
        "id": str(proposal.id),
        "lead_id": str(proposal.record_id) if proposal.record_id else None,
        "customer_id": str(proposal.customer_id) if proposal.customer_id else None,
        "firm_id": str(proposal.firm_id),
        "title": proposal.title,
        "status": proposal.status,
        "expiry_date": str(proposal.expiry_date) if proposal.expiry_date else None,
        "currency": proposal.currency,
        "notes": proposal.notes,
        "intro_text": proposal.intro_text,
        "closing_text": proposal.closing_text,
        "public_token": str(proposal.public_token),
        "token_expires_at": proposal.token_expires_at,
        "view_count": proposal.view_count,
        "first_viewed_at": proposal.first_viewed_at,
        "sent_at": proposal.sent_at,
        "responded_at": proposal.responded_at,
        "total_value": sum((i.total for i in items), Decimal("0")),
        "items": [_item_out(i) for i in items],
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
    }


def _template_item_out(item: ProposalTemplateItem) -> dict:
    return {
        "id": str(item.id),
        "template_id": str(item.template_id),
        "description": item.description,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "discount": item.discount,
        "vat_rate": item.vat_rate,
        "position": item.position,
    }


def _template_out(tmpl: ProposalTemplate) -> dict:
    return {
        "id": str(tmpl.id),
        "firm_id": str(tmpl.firm_id),
        "name": tmpl.name,
        "intro_text": tmpl.intro_text,
        "closing_text": tmpl.closing_text,
        "items": [_template_item_out(i) for i in tmpl.items.all()],
        "created_at": tmpl.created_at,
        "updated_at": tmpl.updated_at,
    }


def _firm_proposal_item_out(item: FirmProposalItem) -> dict:
    return {
        "id": str(item.id),
        "firm_id": str(item.firm_id),
        "description": item.description,
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "discount": item.discount,
        "vat_rate": item.vat_rate,
        "position": item.position,
        "sku": item.sku,
        "notes": item.notes,
        "image_url": item.image_url,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _log_proposal_created_activity(proposal: Proposal, user) -> None:
    """Log a PROPOSAL_CREATED activity on every linked entity's record (if any)."""
    if proposal.record_id:
        Activity.objects.create(
            record_id=proposal.record_id,
            user=user,
            type=ActivityType.PROPOSAL_CREATED,
            content_text=proposal.title,
            metadata={"proposal_id": str(proposal.id)},
        )


def _get_proposal(proposal_id: str, firm) -> Optional[Proposal]:
    try:
        return Proposal.objects.prefetch_related("items").get(
            id=proposal_id, firm=firm
        )
    except Proposal.DoesNotExist:
        return None


def _build_proposal_automation_context(proposal: Proposal) -> dict:
    """Build the evaluation context dict for automation rules fired from a Proposal event."""
    from firms.models import Membership

    record = proposal.record
    customer_name = ""
    customer_email = ""

    # Try to get customer info from record first, then from direct customer link
    if record and record.customer_id:
        try:
            c = record.customer
            customer_name = f"{c.first_name} {c.last_name}".strip()
            customer_email = c.email or ""
        except Exception:  # noqa: BLE001
            pass
    elif proposal.customer_id:
        try:
            c = proposal.customer
            customer_name = f"{c.first_name} {c.last_name}".strip()
            customer_email = c.email or ""
        except Exception:  # noqa: BLE001
            pass

    owner_email = (
        Membership.objects
        .filter(firm_id=proposal.firm_id, role="owner")
        .select_related("user")
        .values_list("user__email", flat=True)
        .first()
    ) or ""

    return {
        "proposal_id": str(proposal.id),
        "proposal_title": proposal.title,
        "proposal_status": proposal.status,
        "record_id": str(record.id) if record else "",
        "record_title": record.title if record else "",
        "record_status": record.status if record else "",
        "firm_id": str(proposal.firm_id),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "owner_email": owner_email,
    }


# ---------------------------------------------------------------------------
# Proposal CRUD — standalone (firm-wide)
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/proposals",
    auth=django_auth,
    response={200: List[ProposalOut], 403: ErrorOut},
)
def list_all_proposals(request, status: Optional[str] = None, lead_id: Optional[str] = None,
                       customer_id: Optional[str] = None):
    """List all proposals for the active firm, with optional filters."""
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    qs = Proposal.objects.filter(firm=request.firm).prefetch_related("items").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if lead_id:
        qs = qs.filter(record_id=lead_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    return 200, [_proposal_out(p) for p in qs]


@proposals_router.post(
    "/proposals",
    auth=django_auth,
    response={201: ProposalOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_standalone_proposal(request, payload: ProposalIn):
    """Create a proposal, optionally linked to any CRM entity."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    import uuid as _uuid

    # Resolve optional entity links
    record = None
    customer = None

    if payload.lead_id:
        try:
            record = PipelineRecord.objects.get(id=payload.lead_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return 404, {"detail": "PipelineRecord not found."}
    if payload.customer_id:
        try:
            customer = Customer.objects.get(id=payload.customer_id, firm=request.firm)
        except Customer.DoesNotExist:
            return 404, {"detail": "Customer not found."}

    proposal = Proposal.objects.create(
        firm=request.firm,
        record=record,
        customer=customer,
        title=payload.title,
        status=payload.status,
        expiry_date=payload.expiry_date or None,
        currency=payload.currency,
        notes=payload.notes,
        intro_text=payload.intro_text,
        closing_text=payload.closing_text,
        public_token=_uuid.uuid4(),
        token_expires_at=tz.now() + timedelta(days=_PUBLIC_LINK_TTL_DAYS),
    )
    _log_proposal_created_activity(proposal, request.user)
    return 201, _proposal_out(proposal)


# ---------------------------------------------------------------------------
# Proposal CRUD — scoped to a PipelineRecord (backward-compatible)
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/opportunities/{record_id}/proposals",
    auth=django_auth,
    response={200: List[ProposalOut], 403: ErrorOut, 404: ErrorOut},
)
def list_proposals(request, record_id: str):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "PipelineRecord not found."}

    proposals = (
        Proposal.objects.filter(record=record)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return 200, [_proposal_out(p) for p in proposals]


@proposals_router.post(
    "/opportunities/{record_id}/proposals",
    auth=django_auth,
    response={201: ProposalOut, 403: ErrorOut, 404: ErrorOut},
)
def create_proposal(request, record_id: str, payload: ProposalIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "PipelineRecord not found."}

    import uuid as _uuid
    proposal = Proposal.objects.create(
        firm=request.firm,
        record=record,
        title=payload.title,
        status=payload.status,
        expiry_date=payload.expiry_date or None,
        currency=payload.currency,
        notes=payload.notes,
        intro_text=payload.intro_text,
        closing_text=payload.closing_text,
        public_token=_uuid.uuid4(),
        token_expires_at=tz.now() + timedelta(days=_PUBLIC_LINK_TTL_DAYS),
    )
    _log_proposal_created_activity(proposal, request.user)
    return 201, _proposal_out(proposal)



@proposals_router.get(
    "/proposals/{proposal_id}",
    auth=django_auth,
    response={200: ProposalOut, 403: ErrorOut, 404: ErrorOut},
)
def get_proposal(request, proposal_id: str):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}
    return 200, _proposal_out(proposal)


@proposals_router.put(
    "/proposals/{proposal_id}",
    auth=django_auth,
    response={200: ProposalOut, 403: ErrorOut, 404: ErrorOut},
)
def update_proposal(request, proposal_id: str, payload: ProposalUpdateIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    update_data = payload.dict(exclude_none=True)
    for field, value in update_data.items():
        setattr(proposal, field, value)
    proposal.save()
    proposal.refresh_from_db()
    return 200, _proposal_out(proposal)


@proposals_router.delete(
    "/proposals/{proposal_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_proposal(request, proposal_id: str):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    perform_soft_delete(proposal, request.user)
    return 204, None


@proposals_router.get(
    "/proposals/{proposal_id}/activities",
    auth=django_auth,
    response={200: List[dict], 403: ErrorOut, 404: ErrorOut},
)
def list_proposal_activities(request, proposal_id: str, page: int = 1, page_size: int = 20):
    """Return the activity timeline for a Proposal, newest first (paginated)."""
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(proposal=proposal).select_related('user').prefetch_related('reactions').order_by("-created_at")[offset:offset + page_size]
    return 200, [_shared_activity_out(a, request.user) for a in activities]


@proposals_router.post(
    "/proposals/{proposal_id}/send",
    auth=django_auth,
    response={200: ProposalOut, 403: ErrorOut, 404: ErrorOut},
)
def send_proposal(request, proposal_id: str):
    """
    Marks the proposal as Sent, regenerates the public token, and resets
    the expiry window so the recipient gets a fresh 30-day link.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    import uuid as _uuid
    proposal.status = ProposalStatus.SENT
    proposal.sent_at = tz.now()
    proposal.public_token = _uuid.uuid4()
    proposal.token_expires_at = tz.now() + timedelta(days=_PUBLIC_LINK_TTL_DAYS)
    proposal.save()

    # Fire workflow automation trigger: proposal_sent
    from crm.tasks import evaluate_automation_rules
    from django.db import transaction
    _automation_ctx = _build_proposal_automation_context(proposal)
    transaction.on_commit(
        lambda ctx=_automation_ctx: evaluate_automation_rules.delay(
            "proposal_sent", str(proposal.firm_id), ctx
        )
    )

    return 200, _proposal_out(proposal)


@proposals_router.post(
    "/proposals/{proposal_id}/apply-template",
    auth=django_auth,
    response={200: ProposalOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def apply_template(request, proposal_id: str, payload: ApplyTemplateIn):
    """
    Applies a ProposalTemplate to the proposal: copies intro/closing text and
    appends the template's line items (preserving existing items).
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    try:
        tmpl = ProposalTemplate.objects.prefetch_related("items").get(
            id=payload.template_id, firm=request.firm
        )
    except ProposalTemplate.DoesNotExist:
        return 400, {"detail": "Template not found."}

    # Set intro/closing from template
    if tmpl.intro_text:
        proposal.intro_text = tmpl.intro_text
    if tmpl.closing_text:
        proposal.closing_text = tmpl.closing_text
    proposal.save()

    # Determine next position
    existing_max = (
        proposal.items.order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    offset = (existing_max + 1) if existing_max is not None else 0

    for tmpl_item in tmpl.items.order_by("position"):
        ProposalItem.objects.create(
            proposal=proposal,
            description=tmpl_item.description,
            quantity=tmpl_item.quantity,
            unit_price=tmpl_item.unit_price,
            discount=tmpl_item.discount,
            vat_rate=tmpl_item.vat_rate,
            position=offset + tmpl_item.position,
        )

    proposal.refresh_from_db()
    return 200, _proposal_out(proposal)


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def request_absolute_url(path: str) -> str:
    """Convert a media path to an absolute URL for WeasyPrint."""
    if path.startswith("http"):
        return path
    media_root = str(settings.MEDIA_ROOT)
    if path.startswith(settings.MEDIA_URL):
        rel = path[len(settings.MEDIA_URL):]
        return f"file://{media_root}/{rel}"
    return path


@proposals_router.get(
    "/proposals/{proposal_id}/pdf",
    auth=django_auth,
)
def download_pdf(request, proposal_id: str):
    try:
        require_membership(request)
    except PermissionDenied:
        return HttpResponse("Forbidden", status=403)

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return HttpResponse("Not found", status=404)

    pdf_bytes = _render_pdf(proposal)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    safe_title = "".join(c for c in proposal.title if c.isalnum() or c in " _-")
    response["Content-Disposition"] = f'attachment; filename="proposal-{safe_title}.pdf"'
    return response


def _render_pdf(proposal: Proposal) -> bytes:
    """Render the proposal as a PDF using WeasyPrint + Jinja2."""
    from jinja2 import Environment, BaseLoader
    import weasyprint

    firm = proposal.firm
    logo_url = ""
    if firm.logo:
        try:
            logo_url = request_absolute_url(firm.logo.url)
        except Exception:
            logo_url = ""

    items = list(proposal.items.all())
    total_value = sum((i.total for i in items), Decimal("0"))

    html_str = _PROPOSAL_HTML_TEMPLATE
    env = Environment(loader=BaseLoader(), autoescape=True)
    tmpl = env.from_string(html_str)
    html = tmpl.render(
        proposal=proposal,
        items=items,
        total_value=total_value,
        firm=firm,
        logo_url=logo_url,
    )
    return weasyprint.HTML(string=html).write_pdf()


_PROPOSAL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1f2937; font-size: 11pt; }
  h1 { font-size: 22pt; margin-bottom: 4px; }
  h2 { font-size: 13pt; margin: 16px 0 6px; }
  .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; border-bottom: 3px solid {{ firm.primary_color or '#dc2626' }}; padding-bottom: 12px; }
  .firm-name { font-size: 16pt; font-weight: bold; color: {{ firm.primary_color or '#dc2626' }}; }
  .logo { max-height: 60px; }
  .status-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 9pt; font-weight: bold; background: #f3f4f6; color: #374151; text-transform: uppercase; }
  .meta { display: flex; gap: 24px; font-size: 9pt; color: #6b7280; margin-bottom: 16px; }
  .meta span strong { color: #374151; }
  .intro, .closing { font-size: 10.5pt; color: #374151; margin-bottom: 16px; line-height: 1.6; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  thead tr { background: {{ firm.primary_color or '#dc2626' }}; color: white; }
  th { padding: 8px 10px; text-align: left; font-size: 9.5pt; }
  td { padding: 7px 10px; font-size: 9.5pt; border-bottom: 1px solid #f3f4f6; }
  tbody tr:nth-child(even) { background: #f9fafb; }
  .text-right { text-align: right; }
  .totals { margin-top: 8px; float: right; min-width: 220px; }
  .totals table { margin-bottom: 0; }
  .totals td { border: none; padding: 3px 6px; }
  .totals .grand-total td { font-weight: bold; font-size: 12pt; border-top: 2px solid {{ firm.primary_color or '#dc2626' }}; }
  .footer { margin-top: 32px; font-size: 8.5pt; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 8px; }
</style>
</head>
<body>
<div class="header">
  <div>
    {% if logo_url %}<img src="{{ logo_url }}" class="logo" alt="Logo"/>{% endif %}
    <div class="firm-name">{{ firm.name }}</div>
  </div>
  <div style="text-align:right">
    <h1>{{ proposal.title }}</h1>
    <span class="status-badge">{{ proposal.status }}</span>
  </div>
</div>

<div class="meta">
  <span><strong>Date:</strong> {{ proposal.created_at.strftime('%Y-%m-%d') }}</span>
  {% if proposal.expiry_date %}<span><strong>Valid until:</strong> {{ proposal.expiry_date }}</span>{% endif %}
  <span><strong>Currency:</strong> {{ proposal.currency }}</span>
</div>

{% if proposal.intro_text %}
<div class="intro">{{ proposal.intro_text }}</div>
{% endif %}

<h2>Line Items</h2>
<table>
  <thead>
    <tr>
      <th style="width:45%">Description</th>
      <th class="text-right" style="width:10%">Qty</th>
      <th class="text-right" style="width:13%">Unit Price</th>
      <th class="text-right" style="width:10%">Disc. %</th>
      <th class="text-right" style="width:10%">VAT %</th>
      <th class="text-right" style="width:12%">Total</th>
    </tr>
  </thead>
  <tbody>
    {% for item in items %}
    <tr>
      <td>{{ item.description }}</td>
      <td class="text-right">{{ item.quantity }}</td>
      <td class="text-right">{{ "%.2f"|format(item.unit_price) }}</td>
      <td class="text-right">{{ item.discount }}%</td>
      <td class="text-right">{{ item.vat_rate }}%</td>
      <td class="text-right">{{ "%.2f"|format(item.total) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<div class="totals">
  <table>
    <tr><td>Subtotal (before disc.)</td><td class="text-right">{{ "%.2f"|format(items|sum(attribute='subtotal')) }} {{ proposal.currency }}</td></tr>
    <tr><td>Discount</td><td class="text-right">-{{ "%.2f"|format(items|sum(attribute='discount_amount')) }} {{ proposal.currency }}</td></tr>
    <tr><td>Tax / VAT</td><td class="text-right">{{ "%.2f"|format(items|sum(attribute='tax')) }} {{ proposal.currency }}</td></tr>
    <tr class="grand-total"><td>Total</td><td class="text-right">{{ "%.2f"|format(total_value) }} {{ proposal.currency }}</td></tr>
  </table>
</div>
<div style="clear:both"></div>

{% if proposal.closing_text %}
<div class="closing">{{ proposal.closing_text }}</div>
{% endif %}

<div class="footer">
  Generated by LeadLab &bull; {{ firm.name }}
</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Proposal Items CRUD
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/proposals/{proposal_id}/items",
    auth=django_auth,
    response={200: List[ProposalItemOut], 403: ErrorOut, 404: ErrorOut},
)
def list_items(request, proposal_id: str):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    return 200, [_item_out(i) for i in proposal.items.order_by("position", "created_at")]


@proposals_router.post(
    "/proposals/{proposal_id}/items",
    auth=django_auth,
    response={201: ProposalItemOut, 403: ErrorOut, 404: ErrorOut},
)
def create_item(request, proposal_id: str, payload: ProposalItemIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    item = ProposalItem.objects.create(
        proposal=proposal,
        **payload.dict(),
    )
    return 201, _item_out(item)


@proposals_router.put(
    "/proposals/{proposal_id}/items/{item_id}",
    auth=django_auth,
    response={200: ProposalItemOut, 403: ErrorOut, 404: ErrorOut},
)
def update_item(request, proposal_id: str, item_id: str, payload: ProposalItemIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    try:
        item = ProposalItem.objects.get(id=item_id, proposal=proposal)
    except ProposalItem.DoesNotExist:
        return 404, {"detail": "Item not found."}

    for field, value in payload.dict().items():
        setattr(item, field, value)
    item.save()
    return 200, _item_out(item)


@proposals_router.delete(
    "/proposals/{proposal_id}/items/{item_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_item(request, proposal_id: str, item_id: str):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    try:
        item = ProposalItem.objects.get(id=item_id, proposal=proposal)
    except ProposalItem.DoesNotExist:
        return 404, {"detail": "Item not found."}

    item.delete()
    return 204, None


@proposals_router.post(
    "/proposals/{proposal_id}/items/reorder",
    auth=django_auth,
    response={200: List[ProposalItemOut], 403: ErrorOut, 404: ErrorOut},
)
def reorder_items(request, proposal_id: str, payload: ItemReorderIn):
    """
    Bulk-update the ``position`` of proposal items.
    Payload: { "items": [{"id": "...", "position": 0}, ...] }
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    for entry in payload.items:
        ProposalItem.objects.filter(
            id=entry.get("id"), proposal=proposal
        ).update(position=entry.get("position", 0))

    items = list(proposal.items.order_by("position", "created_at"))
    return 200, [_item_out(i) for i in items]


# ---------------------------------------------------------------------------
# Proposal Templates CRUD
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/proposal-templates",
    auth=django_auth,
    response={200: List[ProposalTemplateOut], 403: ErrorOut},
)
def list_templates(request):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    templates = ProposalTemplate.objects.filter(firm=request.firm).prefetch_related("items")
    return 200, [_template_out(t) for t in templates]


@proposals_router.post(
    "/proposal-templates",
    auth=django_auth,
    response={201: ProposalTemplateOut, 403: ErrorOut},
)
def create_template(request, payload: ProposalTemplateIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    tmpl = ProposalTemplate.objects.create(firm=request.firm, **payload.dict())
    return 201, _template_out(tmpl)


@proposals_router.get(
    "/proposal-templates/{template_id}",
    auth=django_auth,
    response={200: ProposalTemplateOut, 403: ErrorOut, 404: ErrorOut},
)
def get_template(request, template_id: str):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.prefetch_related("items").get(
            id=template_id, firm=request.firm
        )
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}
    return 200, _template_out(tmpl)


@proposals_router.put(
    "/proposal-templates/{template_id}",
    auth=django_auth,
    response={200: ProposalTemplateOut, 403: ErrorOut, 404: ErrorOut},
)
def update_template(request, template_id: str, payload: ProposalTemplateIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.get(id=template_id, firm=request.firm)
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}

    for field, value in payload.dict().items():
        setattr(tmpl, field, value)
    tmpl.save()
    tmpl.refresh_from_db()
    return 200, _template_out(tmpl)


@proposals_router.delete(
    "/proposal-templates/{template_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_template(request, template_id: str):
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.get(id=template_id, firm=request.firm)
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}

    perform_soft_delete(tmpl, request.user)
    return 204, None


@proposals_router.get(
    "/proposal-templates/{template_id}/items",
    auth=django_auth,
    response={200: List[ProposalTemplateItemOut], 403: ErrorOut, 404: ErrorOut},
)
def list_template_items(request, template_id: str):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.get(id=template_id, firm=request.firm)
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}

    return 200, [_template_item_out(i) for i in tmpl.items.all()]


@proposals_router.post(
    "/proposal-templates/{template_id}/items",
    auth=django_auth,
    response={201: ProposalTemplateItemOut, 403: ErrorOut, 404: ErrorOut},
)
def create_template_item(request, template_id: str, payload: ProposalTemplateItemIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.get(id=template_id, firm=request.firm)
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}

    item = ProposalTemplateItem.objects.create(template=tmpl, **payload.dict())
    return 201, _template_item_out(item)


@proposals_router.put(
    "/proposal-templates/{template_id}/items/{item_id}",
    auth=django_auth,
    response={200: ProposalTemplateItemOut, 403: ErrorOut, 404: ErrorOut},
)
def update_template_item(request, template_id: str, item_id: str, payload: ProposalTemplateItemIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.get(id=template_id, firm=request.firm)
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}

    try:
        item = ProposalTemplateItem.objects.get(id=item_id, template=tmpl)
    except ProposalTemplateItem.DoesNotExist:
        return 404, {"detail": "Item not found."}

    for field, value in payload.dict().items():
        setattr(item, field, value)
    item.save()
    return 200, _template_item_out(item)


@proposals_router.delete(
    "/proposal-templates/{template_id}/items/{item_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_template_item(request, template_id: str, item_id: str):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = ProposalTemplate.objects.get(id=template_id, firm=request.firm)
    except ProposalTemplate.DoesNotExist:
        return 404, {"detail": "Template not found."}

    try:
        item = ProposalTemplateItem.objects.get(id=item_id, template=tmpl)
    except ProposalTemplateItem.DoesNotExist:
        return 404, {"detail": "Item not found."}

    item.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Public proposal link (no auth)
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/public/proposals/{token}",
    auth=None,
    response={200: PublicProposalOut, 404: ErrorOut, 410: ErrorOut},
)
def public_get_proposal(request, token: str):
    """
    Public (no-auth) read-only view of a proposal.
    Increments view_count and records first_viewed_at on first access.
    """
    try:
        proposal = (
            Proposal.objects.select_related("firm")
            .prefetch_related("items")
            .get(public_token=token)
        )
    except Proposal.DoesNotExist:
        return 404, {"detail": "Proposal not found."}

    now = tz.now()
    is_expired = bool(proposal.token_expires_at and proposal.token_expires_at < now)

    # Track view even if expired (so the sender knows)
    if proposal.status == ProposalStatus.SENT:
        Proposal.objects.filter(pk=proposal.pk).update(
            status=ProposalStatus.VIEWED,
            view_count=proposal.view_count + 1,
            first_viewed_at=proposal.first_viewed_at or now,
        )
        proposal.status = ProposalStatus.VIEWED
        proposal.view_count += 1
        if not proposal.first_viewed_at:
            proposal.first_viewed_at = now
    elif proposal.status == ProposalStatus.VIEWED:
        Proposal.objects.filter(pk=proposal.pk).update(
            view_count=proposal.view_count + 1,
        )
        proposal.view_count += 1

    firm = proposal.firm
    logo_url = firm.logo.url if firm.logo else None

    items = list(proposal.items.all())
    total_value = sum((i.total for i in items), Decimal("0"))

    return 200, {
        "id": str(proposal.id),
        "title": proposal.title,
        "status": proposal.status,
        "expiry_date": str(proposal.expiry_date) if proposal.expiry_date else None,
        "currency": proposal.currency,
        "notes": proposal.notes,
        "intro_text": proposal.intro_text,
        "closing_text": proposal.closing_text,
        "total_value": total_value,
        "items": [_item_out(i) for i in items],
        "firm_name": firm.name,
        "firm_logo_url": logo_url,
        "firm_primary_color": firm.primary_color or "#dc2626",
        "is_expired": is_expired,
    }


@proposals_router.post(
    "/public/proposals/{token}/respond",
    auth=None,
    response={200: PublicProposalOut, 400: ErrorOut, 404: ErrorOut, 410: ErrorOut},
)
def public_respond_proposal(request, token: str, payload: PublicProposalRespondIn):
    """
    The proposal recipient accepts or rejects the proposal.
    Logs a PROPOSAL_ACCEPTED or PROPOSAL_REJECTED activity on the record.
    """
    if payload.action not in ("accept", "reject"):
        return 400, {"detail": "action must be 'accept' or 'reject'."}

    try:
        proposal = (
            Proposal.objects.select_related("firm", "record")
            .prefetch_related("items")
            .get(public_token=token)
        )
    except Proposal.DoesNotExist:
        return 404, {"detail": "Proposal not found."}

    now = tz.now()
    is_expired = bool(proposal.token_expires_at and proposal.token_expires_at < now)
    if is_expired:
        return 410, {"detail": "This proposal link has expired."}

    if proposal.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
        return 400, {"detail": "This proposal has already been responded to."}

    new_status = ProposalStatus.ACCEPTED if payload.action == "accept" else ProposalStatus.REJECTED
    activity_type = (
        ActivityType.PROPOSAL_ACCEPTED
        if payload.action == "accept"
        else ActivityType.PROPOSAL_REJECTED
    )

    proposal.status = new_status
    proposal.responded_at = now
    proposal.save(update_fields=["status", "responded_at", "updated_at"])

    if proposal.record_id:
        Activity.objects.create(
            record=proposal.record,
            type=activity_type,
            content_text=f"Proposal '{proposal.title}' was {new_status} via public link.",
            metadata={"proposal_id": str(proposal.id), "proposal_title": proposal.title},
        )

    # Fire workflow automation trigger: proposal_accepted
    if payload.action == "accept":
        from crm.tasks import evaluate_automation_rules
        from django.db import transaction
        _automation_ctx = _build_proposal_automation_context(proposal)
        transaction.on_commit(
            lambda ctx=_automation_ctx: evaluate_automation_rules.delay(
                "proposal_accepted", str(proposal.firm_id), ctx
            )
        )

    firm = proposal.firm
    logo_url = firm.logo.url if firm.logo else None
    items = list(proposal.items.all())
    total_value = sum((i.total for i in items), Decimal("0"))

    return 200, {
        "id": str(proposal.id),
        "title": proposal.title,
        "status": proposal.status,
        "expiry_date": str(proposal.expiry_date) if proposal.expiry_date else None,
        "currency": proposal.currency,
        "notes": proposal.notes,
        "intro_text": proposal.intro_text,
        "closing_text": proposal.closing_text,
        "total_value": total_value,
        "items": [_item_out(i) for i in items],
        "firm_name": firm.name,
        "firm_logo_url": logo_url,
        "firm_primary_color": firm.primary_color or "#dc2626",
        "is_expired": False,
    }


# ---------------------------------------------------------------------------
# Proposal analytics
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/reports/proposal-analytics",
    auth=django_auth,
    response={200: ProposalAnalyticsOut, 403: ErrorOut},
)
def proposal_analytics(request):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    from django.db.models import Avg, Count, F, ExpressionWrapper, DurationField, Q

    qs = Proposal.objects.filter(firm=request.firm)

    totals = qs.aggregate(
        total=Count("id"),
        draft=Count("id", filter=Q(status=ProposalStatus.DRAFT)),
        sent=Count("id", filter=Q(status=ProposalStatus.SENT)),
        viewed=Count("id", filter=Q(status=ProposalStatus.VIEWED)),
        accepted=Count("id", filter=Q(status=ProposalStatus.ACCEPTED)),
        rejected=Count("id", filter=Q(status=ProposalStatus.REJECTED)),
        expired=Count("id", filter=Q(status=ProposalStatus.EXPIRED)),
    )

    total = totals["total"] or 0
    accepted = totals["accepted"] or 0
    rejected = totals["rejected"] or 0
    closed = accepted + rejected

    acceptance_rate = (accepted / closed * 100) if closed else 0.0
    rejection_rate = (rejected / closed * 100) if closed else 0.0

    # avg time-to-open: sent_at → first_viewed_at
    avg_open = (
        qs.filter(sent_at__isnull=False, first_viewed_at__isnull=False)
        .annotate(
            open_duration=ExpressionWrapper(
                F("first_viewed_at") - F("sent_at"), output_field=DurationField()
            )
        )
        .aggregate(avg=Avg("open_duration"))["avg"]
    )
    avg_time_to_open_hours: Optional[float] = None
    if avg_open is not None:
        avg_time_to_open_hours = avg_open.total_seconds() / 3600

    # Per-template stats — how many proposals based on each template
    from crm.models import ProposalTemplate as PT
    template_stats = []
    for tmpl in PT.objects.filter(firm=request.firm):
        # We can't directly trace which proposals used a template (no FK) so we
        # expose a simple count per template name for now.
        template_stats.append({"template_id": str(tmpl.id), "name": tmpl.name})

    return 200, {
        "total": total,
        "draft": totals["draft"] or 0,
        "sent": totals["sent"] or 0,
        "viewed": totals["viewed"] or 0,
        "accepted": accepted,
        "rejected": rejected,
        "expired": totals["expired"] or 0,
        "acceptance_rate": round(acceptance_rate, 1),
        "rejection_rate": round(rejection_rate, 1),
        "avg_time_to_open_hours": avg_time_to_open_hours,
        "template_stats": template_stats,
    }


# ---------------------------------------------------------------------------
# Proposal Items — add from catalog
# ---------------------------------------------------------------------------

@proposals_router.post(
    "/proposals/{proposal_id}/items/from-catalog",
    auth=django_auth,
    response={200: List[ProposalItemOut], 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def add_items_from_catalog(request, proposal_id: str, payload: AddFromCatalogIn):
    """
    Append one or more FirmProposalItem catalog entries as new ProposalItems.
    Payload: { "item_ids": ["<uuid>", ...] }
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    proposal = _get_proposal(proposal_id, request.firm)
    if not proposal:
        return 404, {"detail": "Proposal not found."}

    if not payload.item_ids:
        return 400, {"detail": "item_ids must not be empty."}

    catalog_items = FirmProposalItem.objects.filter(
        firm=request.firm, id__in=payload.item_ids
    )
    if not catalog_items.exists():
        return 404, {"detail": "No matching catalog items found."}

    existing_max = (
        proposal.items.order_by("-position")
        .values_list("position", flat=True)
        .first()
    )
    offset = (existing_max + 1) if existing_max is not None else 0

    created = []
    for idx, ci in enumerate(catalog_items.order_by("position")):
        item = ProposalItem.objects.create(
            proposal=proposal,
            description=ci.description,
            quantity=ci.quantity,
            unit_price=ci.unit_price,
            discount=ci.discount,
            vat_rate=ci.vat_rate,
            position=offset + idx,
        )
        created.append(item)

    return 200, [_item_out(i) for i in created]


# ---------------------------------------------------------------------------
# Firm Proposal Item Catalog CRUD
# ---------------------------------------------------------------------------

@proposals_router.get(
    "/firm-proposal-items",
    auth=django_auth,
    response={200: List[FirmProposalItemOut], 403: ErrorOut},
)
def list_firm_proposal_items(request):
    """List the firm's proposal item catalog."""
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    items = FirmProposalItem.objects.filter(firm=request.firm).order_by("position", "description")
    return 200, [_firm_proposal_item_out(i) for i in items]


@proposals_router.post(
    "/firm-proposal-items",
    auth=django_auth,
    response={201: FirmProposalItemOut, 403: ErrorOut},
)
def create_firm_proposal_item(request, payload: FirmProposalItemIn):
    """Add a new item to the firm's proposal catalog."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    item = FirmProposalItem.objects.create(firm=request.firm, **payload.dict())
    return 201, _firm_proposal_item_out(item)


@proposals_router.put(
    "/firm-proposal-items/{item_id}",
    auth=django_auth,
    response={200: FirmProposalItemOut, 403: ErrorOut, 404: ErrorOut},
)
def update_firm_proposal_item(request, item_id: str, payload: FirmProposalItemIn):
    """Update an existing catalog item."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        item = FirmProposalItem.objects.get(id=item_id, firm=request.firm)
    except FirmProposalItem.DoesNotExist:
        return 404, {"detail": "Catalog item not found."}

    for field, value in payload.dict().items():
        setattr(item, field, value)
    item.save()
    return 200, _firm_proposal_item_out(item)


@proposals_router.delete(
    "/firm-proposal-items/{item_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_firm_proposal_item(request, item_id: str):
    """Delete a catalog item."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        item = FirmProposalItem.objects.get(id=item_id, firm=request.firm)
    except FirmProposalItem.DoesNotExist:
        return 404, {"detail": "Catalog item not found."}

    perform_soft_delete(item, request.user)
    return 204, None
