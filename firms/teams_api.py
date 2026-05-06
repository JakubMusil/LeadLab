"""
Django Ninja API router – Team management (Phase 6)

Endpoints:
    GET    /firms/{firm_id}/teams                               — list teams
    POST   /firms/{firm_id}/teams                               — create team
    PATCH  /firms/{firm_id}/teams/{team_id}                     — update team
    DELETE /firms/{firm_id}/teams/{team_id}                     — delete team
    POST   /firms/{firm_id}/teams/{team_id}/members/{membership_id}  — add member
    DELETE /firms/{firm_id}/teams/{team_id}/members/{membership_id}  — remove member
"""
from typing import List, Optional

from django.db import transaction
from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import (
    AuthenticationRequired,
    FirmNotFound,
    PermissionDenied,
    require_permission,
)
from firms.models import Firm, Membership, Team, TeamMembership
from firms.permissions import Permission

router = Router(tags=["teams"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TeamMemberOut(Schema):
    membership_id: str
    user_id: str
    user_email: str
    user_full_name: str


class TeamOut(Schema):
    id: str
    name: str
    slug: str
    color: str
    member_count: int
    members: List[TeamMemberOut]


class TeamCreateIn(Schema):
    name: str
    color: str = "#6366f1"


class TeamUpdateIn(Schema):
    name: Optional[str] = None
    color: Optional[str] = None


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _team_out(team: Team) -> dict:
    memberships = (
        TeamMembership.objects
        .filter(team=team)
        .select_related("membership__user")
    )
    members = []
    for tm in memberships:
        m = tm.membership
        members.append({
            "membership_id": str(m.id),
            "user_id": str(m.user_id),
            "user_email": m.user.email,
            "user_full_name": m.user.full_name,
        })
    return {
        "id": str(team.id),
        "name": team.name,
        "slug": team.slug,
        "color": team.color,
        "member_count": len(members),
        "members": members,
    }


def _get_firm_and_membership(request, firm_id: str):
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        raise FirmNotFound("Firm not found.")
    membership = getattr(request, "membership", None)
    if membership is None or membership.firm_id != firm.pk:
        raise PermissionDenied("You are not a member of this Firm.")
    return firm, membership


# ---------------------------------------------------------------------------
# Team CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/{firm_id}/teams",
    auth=django_auth,
    response={200: List[TeamOut], 403: ErrorOut, 404: ErrorOut},
)
def list_teams(request, firm_id: str):
    """List all teams for a firm. Any member may read."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except PermissionDenied:
        return 403, {"detail": "Access denied."}

    teams = Team.objects.filter(firm=firm).order_by("name")
    return 200, [_team_out(t) for t in teams]


@router.post(
    "/{firm_id}/teams",
    auth=django_auth,
    response={201: TeamOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_team(request, firm_id: str, payload: TeamCreateIn):
    """Create a new team. Requires ``team.manage``."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.TEAM_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "team.manage permission required."}

    with transaction.atomic():
        team = Team.objects.create(
            firm=firm,
            name=payload.name,
            color=payload.color,
        )

    return 201, _team_out(team)


@router.patch(
    "/{firm_id}/teams/{team_id}",
    auth=django_auth,
    response={200: TeamOut, 403: ErrorOut, 404: ErrorOut},
)
def update_team(request, firm_id: str, team_id: str, payload: TeamUpdateIn):
    """Update a team's name or colour. Requires ``team.manage``."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.TEAM_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "team.manage permission required."}

    try:
        team = Team.objects.get(id=team_id, firm=firm)
    except Team.DoesNotExist:
        return 404, {"detail": "Team not found."}

    update_fields = []
    if payload.name is not None:
        team.name = payload.name
        update_fields.append("name")
    if payload.color is not None:
        team.color = payload.color
        update_fields.append("color")
    if update_fields:
        team.save(update_fields=update_fields)

    return 200, _team_out(team)


@router.delete(
    "/{firm_id}/teams/{team_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_team(request, firm_id: str, team_id: str):
    """Delete a team. Requires ``team.manage``."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.TEAM_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "team.manage permission required."}

    try:
        team = Team.objects.get(id=team_id, firm=firm)
    except Team.DoesNotExist:
        return 404, {"detail": "Team not found."}

    team.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Team membership management
# ---------------------------------------------------------------------------

@router.post(
    "/{firm_id}/teams/{team_id}/members/{membership_id}",
    auth=django_auth,
    response={201: TeamOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def add_team_member(request, firm_id: str, team_id: str, membership_id: str):
    """Add a firm member to a team. Requires ``team.manage``."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.TEAM_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "team.manage permission required."}

    try:
        team = Team.objects.get(id=team_id, firm=firm)
    except Team.DoesNotExist:
        return 404, {"detail": "Team not found."}

    try:
        target_membership = Membership.objects.get(id=membership_id, firm=firm)
    except Membership.DoesNotExist:
        return 404, {"detail": "Membership not found in this firm."}

    _, created = TeamMembership.objects.get_or_create(
        team=team,
        membership=target_membership,
    )
    if not created:
        return 400, {"detail": "Member is already in this team."}

    return 201, _team_out(team)


@router.delete(
    "/{firm_id}/teams/{team_id}/members/{membership_id}",
    auth=django_auth,
    response={200: TeamOut, 403: ErrorOut, 404: ErrorOut},
)
def remove_team_member(request, firm_id: str, team_id: str, membership_id: str):
    """Remove a firm member from a team. Requires ``team.manage``."""
    try:
        firm, _ = _get_firm_and_membership(request, firm_id)
        require_permission(request, Permission.TEAM_MANAGE)
    except FirmNotFound:
        return 404, {"detail": "Firm not found."}
    except (PermissionDenied, AuthenticationRequired):
        return 403, {"detail": "team.manage permission required."}

    try:
        team = Team.objects.get(id=team_id, firm=firm)
    except Team.DoesNotExist:
        return 404, {"detail": "Team not found."}

    try:
        tm = TeamMembership.objects.get(team=team, membership__id=membership_id, membership__firm=firm)
    except TeamMembership.DoesNotExist:
        return 404, {"detail": "Member is not in this team."}

    tm.delete()
    return 200, _team_out(team)
