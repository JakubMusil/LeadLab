"""
Pipeline Configuration API — Phase 3

Endpoints for managing Categories, Stages, and CategoryFields.

All endpoints are mounted at /api/v1/crm/ via leadlab/api.py.

Permission model:
  - GET endpoints: any firm member
  - POST/PATCH/DELETE: owner or admin only
"""
from __future__ import annotations

import logging
from typing import List, Optional

from django.db import transaction
from ninja import Router, Schema
from ninja.security import django_auth

from crm.events import broadcast_event
from crm.models import Category, CategoryField, Stage, PipelineRecord
from firms.auth import InvitationRole, PermissionDenied, require_membership

pipeline_config_router = Router(tags=["pipeline-config"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared error schema
# ---------------------------------------------------------------------------

class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Category schemas
# ---------------------------------------------------------------------------

class CategoryOut(Schema):
    id: str
    firm_id: str
    name: str
    slug: str
    icon: str
    color: str
    order: int
    is_active: bool
    created_at: str


class CategoryIn(Schema):
    name: str
    icon: str = ""
    color: str = ""
    order: int = 0
    is_active: bool = True


class CategoryUpdateIn(Schema):
    name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    order: Optional[int] = None
    is_active: Optional[bool] = None


def _category_out(c: Category) -> dict:
    return {
        "id": str(c.id),
        "firm_id": str(c.firm_id),
        "name": c.name,
        "slug": c.slug,
        "icon": c.icon,
        "color": c.color,
        "order": c.order,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Stage schemas
# ---------------------------------------------------------------------------

class StageOut(Schema):
    id: str
    category_id: str
    name: str
    label: str
    color: str
    order: int
    is_terminal: bool
    is_won: bool
    created_at: str


class StageIn(Schema):
    name: str
    label: str = ""
    color: str = ""
    order: int = 0
    is_terminal: bool = False
    is_won: bool = False


class StageUpdateIn(Schema):
    name: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None
    order: Optional[int] = None
    is_terminal: Optional[bool] = None
    is_won: Optional[bool] = None


def _stage_out(s: Stage) -> dict:
    return {
        "id": str(s.id),
        "category_id": str(s.category_id),
        "name": s.name,
        "label": s.label,
        "color": s.color,
        "order": s.order,
        "is_terminal": s.is_terminal,
        "is_won": s.is_won,
        "created_at": s.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# CategoryField schemas
# ---------------------------------------------------------------------------

class CategoryFieldOut(Schema):
    id: str
    category_id: str
    field_key: str
    is_visible: bool
    is_required: bool
    order: int
    value_type: str
    widget: str
    validation_rules: dict
    label_override: str
    help_text_override: str


class CategoryFieldIn(Schema):
    field_key: str
    is_visible: bool = True
    is_required: bool = False
    order: int = 0
    value_type: str = "text"
    widget: str = "auto"
    validation_rules: dict = {}
    label_override: str = ""
    help_text_override: str = ""


class CategoryFieldUpdateIn(Schema):
    is_visible: Optional[bool] = None
    is_required: Optional[bool] = None
    order: Optional[int] = None
    value_type: Optional[str] = None
    widget: Optional[str] = None
    validation_rules: Optional[dict] = None
    label_override: Optional[str] = None
    help_text_override: Optional[str] = None


def _field_out(f: CategoryField) -> dict:
    return {
        "id": str(f.id),
        "category_id": str(f.category_id),
        "field_key": f.field_key,
        "is_visible": f.is_visible,
        "is_required": f.is_required,
        "order": f.order,
        "value_type": f.value_type,
        "widget": f.widget,
        "validation_rules": f.validation_rules or {},
        "label_override": f.label_override or "",
        "help_text_override": f.help_text_override or "",
    }

def _validate_field_payload(payload_dict: dict) -> Optional[str]:
    """Return an error string if validation fails, otherwise None."""
    widget = payload_dict.get("widget")
    value_type = payload_dict.get("value_type")
    rules = payload_dict.get("validation_rules") or {}

    # select / multiselect widgets require options
    if widget in ("select", "multiselect") or value_type in ("select", "multiselect"):
        options = rules.get("options")
        if not isinstance(options, list) or len(options) == 0:
            return "Fields of type 'select' or 'multiselect' require at least one option in validation_rules.options."

    valid_value_types = [k for k, _ in CategoryField.VALUE_TYPE_CHOICES]
    if value_type and value_type not in valid_value_types:
        return f"Invalid value_type. Valid choices: {valid_value_types}"

    valid_widgets = [k for k, _ in CategoryField.WIDGET_CHOICES]
    if widget and widget not in valid_widgets:
        return f"Invalid widget. Valid choices: {valid_widgets}"

    return None




@pipeline_config_router.get(
    "/categories",
    auth=django_auth,
    response={200: List[CategoryOut], 403: ErrorOut},
)
def list_categories(request):
    """List all categories for the current firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    categories = Category.objects.filter(firm=request.firm).order_by("order", "name")
    return 200, [_category_out(c) for c in categories]


@pipeline_config_router.post(
    "/categories",
    auth=django_auth,
    response={201: CategoryOut, 400: ErrorOut, 403: ErrorOut},
)
def create_category(request, payload: CategoryIn):
    """Create a new category. Requires admin or owner role."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    from django.utils.text import slugify
    base_slug = slugify(payload.name)
    slug = base_slug
    suffix = 1
    while Category.objects.filter(firm=request.firm, slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    category = Category.objects.create(
        firm=request.firm,
        name=payload.name,
        slug=slug,
        icon=payload.icon,
        color=payload.color,
        order=payload.order,
        is_active=payload.is_active,
    )
    broadcast_event(firm=request.firm, event="category.updated", payload=_category_out(category))
    return 201, _category_out(category)


@pipeline_config_router.patch(
    "/categories/{category_id}",
    auth=django_auth,
    response={200: CategoryOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_category(request, category_id: str, payload: CategoryUpdateIn):
    """Update a category's name, color, icon, order, or active status."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    update_data = payload.dict(exclude_none=True)
    if "name" in update_data:
        # Re-generate slug only if name changes; preserve custom slug otherwise.
        from django.utils.text import slugify
        base_slug = slugify(update_data["name"])
        slug = base_slug
        suffix = 1
        while Category.objects.filter(firm=request.firm, slug=slug).exclude(id=category_id).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        category.slug = slug

    for field, value in update_data.items():
        setattr(category, field, value)
    category.save()

    broadcast_event(firm=request.firm, event="category.updated", payload=_category_out(category))
    return 200, _category_out(category)


@pipeline_config_router.delete(
    "/categories/{category_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut, 409: ErrorOut},
)
def delete_category(request, category_id: str):
    """Delete a category. Returns 409 if any records reference it."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    if PipelineRecord.objects.filter(category=category).exists():
        return 409, {"detail": "Cannot delete category with existing records."}

    category.delete()
    broadcast_event(firm=request.firm, event="category.updated", payload={"id": category_id, "deleted": True})
    return 204, None


# ===========================================================================
# STAGE ENDPOINTS
# ===========================================================================

@pipeline_config_router.get(
    "/categories/{category_id}/stages",
    auth=django_auth,
    response={200: List[StageOut], 403: ErrorOut, 404: ErrorOut},
)
def list_stages(request, category_id: str):
    """List all stages for a category."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    stages = Stage.objects.filter(category=category).order_by("order")
    return 200, [_stage_out(s) for s in stages]


@pipeline_config_router.post(
    "/categories/{category_id}/stages",
    auth=django_auth,
    response={201: StageOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_stage(request, category_id: str, payload: StageIn):
    """Create a stage within a category. Requires admin or owner role."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    # Ensure uniqueness of order within category
    order = payload.order
    if Stage.objects.filter(category=category, order=order).exists():
        max_order = Stage.objects.filter(category=category).order_by("-order").values_list("order", flat=True).first()
        order = (max_order or 0) + 1

    stage = Stage.objects.create(
        category=category,
        name=payload.name,
        label=payload.label,
        color=payload.color,
        order=order,
        is_terminal=payload.is_terminal,
        is_won=payload.is_won,
    )
    broadcast_event(firm=request.firm, event="category.updated", payload={"category_id": category_id})
    return 201, _stage_out(stage)


@pipeline_config_router.patch(
    "/categories/{category_id}/stages/{stage_id}",
    auth=django_auth,
    response={200: StageOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_stage(request, category_id: str, stage_id: str, payload: StageUpdateIn):
    """Update a stage's properties."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    try:
        stage = Stage.objects.get(id=stage_id, category=category)
    except Stage.DoesNotExist:
        return 404, {"detail": "Stage not found."}

    update_data = payload.dict(exclude_none=True)
    if "order" in update_data:
        new_order = update_data["order"]
        # Shift conflicting stage out of the way within the same transaction
        with transaction.atomic():
            Stage.objects.filter(category=category, order=new_order).exclude(id=stage_id).update(
                order=new_order + 1000
            )
            for field, value in update_data.items():
                setattr(stage, field, value)
            stage.save()
    else:
        for field, value in update_data.items():
            setattr(stage, field, value)
        stage.save()

    broadcast_event(firm=request.firm, event="category.updated", payload={"category_id": category_id})
    return 200, _stage_out(stage)


@pipeline_config_router.delete(
    "/categories/{category_id}/stages/{stage_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut, 409: ErrorOut},
)
def delete_stage(request, category_id: str, stage_id: str):
    """Delete a stage. Returns 409 if records use this stage."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    try:
        stage = Stage.objects.get(id=stage_id, category=category)
    except Stage.DoesNotExist:
        return 404, {"detail": "Stage not found."}

    if PipelineRecord.objects.filter(current_stage=stage).exists():
        return 409, {"detail": "Cannot delete stage that is currently used by records."}

    stage.delete()
    broadcast_event(firm=request.firm, event="category.updated", payload={"category_id": category_id})
    return 204, None


# ===========================================================================
# CATEGORYFIELD ENDPOINTS
# ===========================================================================

@pipeline_config_router.get(
    "/categories/{category_id}/fields",
    auth=django_auth,
    response={200: List[CategoryFieldOut], 403: ErrorOut, 404: ErrorOut},
)
def list_fields(request, category_id: str):
    """List all configured fields for a category."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    fields = CategoryField.objects.filter(category=category).order_by("order")
    return 200, [_field_out(f) for f in fields]


@pipeline_config_router.post(
    "/categories/{category_id}/fields/{field_key}",
    auth=django_auth,
    response={200: CategoryFieldOut, 201: CategoryFieldOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_field(request, category_id: str, field_key: str, payload: CategoryFieldUpdateIn):
    """Enable or update a field for a category. Returns 201 on creation, 200 if already exists."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    valid_keys = [k for k, _ in CategoryField.FIELD_KEY_CHOICES]
    if field_key not in valid_keys:
        return 400, {"detail": f"Invalid field_key. Valid keys: {valid_keys}"}

    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    err = _validate_field_payload(update_data)
    if err:
        return 400, {"detail": err}

    field, created = CategoryField.objects.update_or_create(
        category=category,
        field_key=field_key,
        defaults=update_data,
    )
    return 201 if created else 200, _field_out(field)


@pipeline_config_router.patch(
    "/categories/{category_id}/fields/{field_key}",
    auth=django_auth,
    response={200: CategoryFieldOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_field(request, category_id: str, field_key: str, payload: CategoryFieldUpdateIn):
    """Update an existing field configuration."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    try:
        field = CategoryField.objects.get(category=category, field_key=field_key)
    except CategoryField.DoesNotExist:
        return 404, {"detail": "Field not found."}

    update_data = payload.dict(exclude_none=True)
    err = _validate_field_payload(update_data)
    if err:
        return 400, {"detail": err}
    for k, v in update_data.items():
        setattr(field, k, v)
    field.save()
    return 200, _field_out(field)


@pipeline_config_router.delete(
    "/categories/{category_id}/fields/{field_key}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_field(request, category_id: str, field_key: str):
    """Remove a field configuration from a category."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    try:
        field = CategoryField.objects.get(category=category, field_key=field_key)
    except CategoryField.DoesNotExist:
        return 404, {"detail": "Field not found."}

    field.delete()
    return 204, None
