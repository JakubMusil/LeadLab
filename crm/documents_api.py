"""
Documents API — Phase 4.3

Endpoints:
  /api/v1/erp/documents           LIST (with filters) + UPLOAD (multipart)
  /api/v1/erp/documents/{id}      GET / DELETE
"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from django.http import HttpRequest
from ninja import File, Router, Schema, UploadedFile
from ninja.security import django_auth

from crm.models import Customer, Document, Lead, Management, Proposal, Realization, Task
from firms.auth import require_active_subscription, require_membership

documents_router = Router(tags=["documents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _firm(request):
    return getattr(request, "firm", None)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DocumentOut(Schema):
    id: str
    firm_id: str
    name: str
    content_type: str
    size_bytes: int

    # Entity links (optional)
    lead_id: Optional[str]
    lead_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    realization_id: Optional[str]
    realization_title: Optional[str]
    management_id: Optional[str]
    management_title: Optional[str]
    task_id: Optional[str]
    task_title: Optional[str]
    proposal_id: Optional[str]
    proposal_title: Optional[str]

    # Authorship
    uploaded_by_id: Optional[str]
    uploaded_by_name: Optional[str]

    file_url: str
    created_at: dt.datetime


def _doc_out(doc: Document, request: HttpRequest) -> DocumentOut:
    """Serialise a Document instance into DocumentOut."""
    file_url = request.build_absolute_uri(doc.file.url) if doc.file else ""

    customer_name = None
    if doc.customer:
        customer_name = f"{doc.customer.first_name} {doc.customer.last_name}".strip() or doc.customer.email

    uploader_name = None
    if doc.uploaded_by:
        full = f"{doc.uploaded_by.first_name} {doc.uploaded_by.last_name}".strip()
        uploader_name = full or doc.uploaded_by.email

    return DocumentOut(
        id=str(doc.id),
        firm_id=str(doc.firm_id),
        name=doc.name,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        lead_id=str(doc.lead_id) if doc.lead_id else None,
        lead_title=doc.lead.title if doc.lead else None,
        customer_id=str(doc.customer_id) if doc.customer_id else None,
        customer_name=customer_name,
        realization_id=str(doc.realization_id) if doc.realization_id else None,
        realization_title=doc.realization.title if doc.realization else None,
        management_id=str(doc.management_id) if doc.management_id else None,
        management_title=doc.management.title if doc.management else None,
        task_id=str(doc.task_id) if doc.task_id else None,
        task_title=doc.task.title if doc.task else None,
        proposal_id=str(doc.proposal_id) if doc.proposal_id else None,
        proposal_title=doc.proposal.title if doc.proposal else None,
        uploaded_by_id=str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
        uploaded_by_name=uploader_name,
        file_url=file_url,
        created_at=doc.created_at,
    )


# ---------------------------------------------------------------------------
# List + Upload
# ---------------------------------------------------------------------------

@documents_router.get("/documents", response=List[DocumentOut], auth=django_auth)
def list_documents(
    request: HttpRequest,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    realization_id: Optional[str] = None,
    management_id: Optional[str] = None,
    task_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """List documents for the active firm with optional entity filters."""
    firm = _firm(request)
    member = require_membership(request, firm)
    require_active_subscription(firm)

    qs = Document.objects.filter(firm=firm).select_related(
        "lead", "customer", "realization", "management", "task", "proposal", "uploaded_by"
    )

    if lead_id:
        qs = qs.filter(lead_id=lead_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if realization_id:
        qs = qs.filter(realization_id=realization_id)
    if management_id:
        qs = qs.filter(management_id=management_id)
    if task_id:
        qs = qs.filter(task_id=task_id)
    if proposal_id:
        qs = qs.filter(proposal_id=proposal_id)
    if search:
        qs = qs.filter(name__icontains=search)

    offset = (page - 1) * page_size
    qs = qs[offset: offset + page_size]

    return [_doc_out(d, request) for d in qs]


@documents_router.post("/documents", response=DocumentOut, auth=django_auth)
def upload_document(
    request: HttpRequest,
    file: UploadedFile = File(...),
    name: Optional[str] = None,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    realization_id: Optional[str] = None,
    management_id: Optional[str] = None,
    task_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
):
    """Upload a new document and optionally link it to a CRM entity."""
    firm = _firm(request)
    member = require_membership(request, firm)
    require_active_subscription(firm)

    display_name = name or file.name or "unnamed"
    content_type = file.content_type or ""
    size_bytes = file.size or 0

    # Validate entity links exist and belong to the firm
    lead = None
    if lead_id:
        lead = Lead.objects.filter(firm=firm, id=lead_id).first()

    customer = None
    if customer_id:
        customer = Customer.objects.filter(firm=firm, id=customer_id).first()

    realization = None
    if realization_id:
        realization = Realization.objects.filter(firm=firm, id=realization_id).first()

    management = None
    if management_id:
        management = Management.objects.filter(firm=firm, id=management_id).first()

    task = None
    if task_id:
        task = Task.objects.filter(firm=firm, id=task_id).first()

    proposal = None
    if proposal_id:
        proposal = Proposal.objects.filter(firm=firm, id=proposal_id).first()

    doc = Document.objects.create(
        firm=firm,
        name=display_name,
        file=file,
        content_type=content_type,
        size_bytes=size_bytes,
        uploaded_by=request.user,
        lead=lead,
        customer=customer,
        realization=realization,
        management=management,
        task=task,
        proposal=proposal,
    )

    return _doc_out(doc, request)


# ---------------------------------------------------------------------------
# Get single document
# ---------------------------------------------------------------------------

@documents_router.get("/documents/{document_id}", response=DocumentOut, auth=django_auth)
def get_document(request: HttpRequest, document_id: str):
    """Get a single document by ID."""
    firm = _firm(request)
    member = require_membership(request, firm)

    doc = Document.objects.filter(firm=firm, id=document_id).select_related(
        "lead", "customer", "realization", "management", "task", "proposal", "uploaded_by"
    ).first()
    if not doc:
        return 404, {"detail": "Document not found"}

    return _doc_out(doc, request)


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------

@documents_router.delete("/documents/{document_id}", auth=django_auth)
def delete_document(request: HttpRequest, document_id: str):
    """Delete a document by ID. The actual file is removed from storage."""
    firm = _firm(request)
    member = require_membership(request, firm)

    doc = Document.objects.filter(firm=firm, id=document_id).first()
    if not doc:
        return 404, {"detail": "Document not found"}

    # Delete the physical file from storage
    if doc.file:
        doc.file.delete(save=False)

    doc.delete()
    return {"success": True}
