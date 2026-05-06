"""
Django Ninja router – API Tokens

Endpoints for creating, listing, and revoking personal API tokens.
All endpoints enforce:
  1. Session or Bearer token authentication.
  2. Membership in the target Firm.
  3. Only the token owner (or Admin/Owner) may revoke a token.
"""

from typing import List, Optional

from django.utils import timezone as tz
from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import InvitationRole, MembershipRole, PermissionDenied, require_membership
from firms.models import APIToken, Firm, Membership
from firms.token_auth import BearerTokenAuth

router = Router(tags=["api-tokens"])

_auth = [django_auth, BearerTokenAuth()]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class APITokenOut(Schema):
    id: str
    name: str
    prefix: str
    created_at: str
    last_used_at: Optional[str]
    expires_at: Optional[str]
    revoked_at: Optional[str]
    is_active: bool


class APITokenCreateOut(APITokenOut):
    """Returned only at creation time — includes the plain-text token."""
    token: str


class APITokenIn(Schema):
    name: str


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_out(t: APIToken) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "prefix": t.prefix,
        "created_at": t.created_at.isoformat(),
        "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None,
        "is_active": t.is_active,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{firm_id}/tokens",
    auth=_auth,
    response={200: List[APITokenOut], 403: ErrorOut},
)
def list_tokens(request, firm_id: str):
    """List all API tokens for a Firm (members only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found."}

    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    tokens = APIToken.objects.filter(firm=firm).order_by("-created_at")
    return 200, [_token_out(t) for t in tokens]


@router.post(
    "/{firm_id}/tokens",
    auth=_auth,
    response={201: APITokenCreateOut, 403: ErrorOut},
)
def create_token(request, firm_id: str, payload: APITokenIn):
    """
    Create a new API token for the authenticated user within a Firm.

    The plain-text token value is returned **once** in the response body
    and is never stored; save it immediately.
    """
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found."}

    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    if not payload.name.strip():
        return 403, {"detail": "Token name is required."}

    token_obj, plain_token = APIToken.create_for_user(
        firm=firm,
        user=request.user,
        name=payload.name.strip(),
    )
    return 201, {**_token_out(token_obj), "token": plain_token}


@router.delete(
    "/{firm_id}/tokens/{token_id}",
    auth=_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def revoke_token(request, firm_id: str, token_id: str):
    """
    Revoke (soft-delete) an API token.

    Admin/Owner members may revoke any token in the Firm.
    Workers may only revoke their own tokens.
    """
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    try:
        token_obj = APIToken.objects.get(id=token_id, firm=firm)
    except APIToken.DoesNotExist:
        return 404, {"detail": "Token not found."}

    # Workers can only revoke their own tokens.
    if not membership.is_admin_or_above and token_obj.user != request.user:
        return 403, {"detail": "You do not have permission to revoke this token."}

    if token_obj.revoked_at is None:
        token_obj.revoked_at = tz.now()
        token_obj.save(update_fields=["revoked_at"])

    return 204, None
