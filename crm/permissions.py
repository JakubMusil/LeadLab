"""
crm.permissions
===============
Phase 4 – Permissions resolver & query scoping.

Provides:

* ``resolve_effective_permissions(membership)`` – collects all Permission codes
  the given membership holds (via its ``Role`` objects from the DB).
* ``resolve_scope(membership, permission)`` – returns the widest ``Scope`` the
  membership has for a given permission (derived from ``default_scope`` +
  ``CategoryGrant`` entries).
* ``filter_records_qs(qs, request)``   – scope-aware PipelineRecord queryset.
* ``filter_activities_qs(qs, request)`` – scope-aware Activity queryset.
* ``filter_proposals_qs(qs, request)`` – scope-aware Proposal queryset.
* ``filter_tasks_qs(qs, request)``     – scope-aware Task queryset.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db.models import Q, QuerySet
from django.utils import timezone

from firms.permissions import Permission, Scope

if TYPE_CHECKING:
    from django.http import HttpRequest
    from firms.models import Membership

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Ordered list of scopes from narrowest to widest.
_SCOPE_ORDER: list[str] = [
    Scope.OWN,
    Scope.CATEGORY,
    Scope.TEAM,
    Scope.ALL,
]


def _scope_rank(scope: str) -> int:
    """Return a numeric rank for a scope string (higher = wider access)."""
    try:
        return _SCOPE_ORDER.index(scope)
    except ValueError:
        return 0


def _wider_scope(a: str, b: str) -> str:
    """Return the wider of the two scope strings."""
    return a if _scope_rank(a) >= _scope_rank(b) else b


# ---------------------------------------------------------------------------
# resolve_effective_permissions
# ---------------------------------------------------------------------------


def resolve_effective_permissions(membership: "Membership") -> set[str]:
    """
    Return the set of permission *codes* (strings) that *membership* holds
    according to its assigned ``Role`` objects.

    Falls back to the legacy ``LEGACY_ROLE_PERMISSIONS`` map when the
    membership has no ``roles`` assigned (e.g. data migration not yet run).
    """
    try:
        codes: set[str] = set(
            membership.roles.values_list("permissions__code", flat=True)
        )
        # Filter out None values that come from roles without any permissions
        codes.discard(None)
    except Exception:  # roles relation not yet available (e.g. test setup)
        codes = set()

    if not codes:
        # Fallback to legacy map so pre-migration memberships still work.
        # Use ``primary_role`` (which prefers M2M roles over the legacy CharField)
        # so any out-of-band role assignment is still reflected here.
        from firms.permissions import LEGACY_ROLE_PERMISSIONS
        legacy_perms = LEGACY_ROLE_PERMISSIONS.get(membership.primary_role, frozenset())
        codes = {p.value for p in legacy_perms}

    return codes


# ---------------------------------------------------------------------------
# resolve_scope
# ---------------------------------------------------------------------------


def resolve_scope(membership: "Membership", permission: Permission | str) -> str:
    """
    Return the *widest* scope the membership has for *permission*.

    Resolution order (widest wins):
    1. ``Membership.default_scope`` (set by admin at member management time)
    2. Active ``CategoryGrant`` entries for the membership's user
       (if any grant exists → scope becomes at least ``Scope.CATEGORY``)
    3. Owner shortcut → always ``Scope.ALL``
    """
    # Owner always gets ALL scope
    if membership.is_owner:
        return Scope.ALL

    effective = membership.default_scope or Scope.OWN

    # If there are any active CategoryGrant entries for this user, the effective
    # scope is at least CATEGORY.
    try:
        now = timezone.now()
        user_id = membership.user_id
        has_category_grant = (
            _get_category_grant_model()
            .objects.filter(
                principal_type="user",
                principal_id=user_id,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .exists()
        )
        if has_category_grant:
            effective = _wider_scope(effective, Scope.CATEGORY)
    except Exception:
        pass

    return effective


# ---------------------------------------------------------------------------
# Lazy model accessors (avoid circular imports at module load time)
# ---------------------------------------------------------------------------


def _get_category_grant_model():
    from crm.models import CategoryGrant  # noqa: PLC0415
    return CategoryGrant


def _get_record_grant_model():
    from crm.models import RecordGrant  # noqa: PLC0415
    return RecordGrant


# ---------------------------------------------------------------------------
# filter_records_qs
# ---------------------------------------------------------------------------


def filter_records_qs(qs: QuerySet, request: "HttpRequest") -> QuerySet:
    """
    Return *qs* filtered to records the requesting user may see.
    """
    membership: "Membership | None" = getattr(request, "membership", None)
    if membership is None:
        return qs.none()

    # Owner sees everything
    if membership.is_owner:
        return qs

    scope = resolve_scope(membership, Permission.RECORD_VIEW)
    user = request.user
    now = timezone.now()

    if scope == Scope.ALL:
        return qs

    # Build the base scope filter
    if scope == Scope.OWN:
        scope_filter = Q(created_by=user) | Q(assigned_to=user)
    elif scope == Scope.TEAM:
        team = membership.team
        if team is not None:
            # Records assigned to any member of the user's team
            team_member_ids = (
                team.team_memberships.values_list("membership__user_id", flat=True)
            )
            scope_filter = Q(assigned_to__in=team_member_ids) | Q(created_by=user) | Q(assigned_to=user)
        else:
            scope_filter = Q(created_by=user) | Q(assigned_to=user)
    elif scope == Scope.CATEGORY:
        # Collect category IDs granted to this user (directly or via team)
        CategoryGrant = _get_category_grant_model()
        granted_category_ids = list(
            CategoryGrant.objects.filter(
                principal_type="user",
                principal_id=user.pk,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .values_list("category_id", flat=True)
        )
        # Also collect from teams the user belongs to
        team_ids = list(
            membership.team_memberships.values_list("team_id", flat=True)
        )
        if team_ids:
            team_category_ids = list(
                CategoryGrant.objects.filter(
                    principal_type="team",
                    principal_id__in=team_ids,
                )
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
                .values_list("category_id", flat=True)
            )
            granted_category_ids = list(set(granted_category_ids) | set(team_category_ids))

        scope_filter = (
            Q(category_id__in=granted_category_ids)
            | Q(created_by=user)
            | Q(assigned_to=user)
        )
    else:
        # Fallback to own
        scope_filter = Q(created_by=user) | Q(assigned_to=user)

    # Additionally include records where the user has an explicit RecordGrant
    RecordGrant = _get_record_grant_model()
    directly_granted_ids = list(
        RecordGrant.objects.filter(
            principal_type="user",
            principal_id=user.pk,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .values_list("record_id", flat=True)
    )
    # Team-based record grants
    team_ids = list(
        membership.team_memberships.values_list("team_id", flat=True)
    )
    if team_ids:
        team_granted_ids = list(
            RecordGrant.objects.filter(
                principal_type="team",
                principal_id__in=team_ids,
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .values_list("record_id", flat=True)
        )
        directly_granted_ids = list(set(directly_granted_ids) | set(team_granted_ids))

    if directly_granted_ids:
        return qs.filter(scope_filter | Q(id__in=directly_granted_ids))

    return qs.filter(scope_filter)


# ---------------------------------------------------------------------------
# filter_activities_qs
# ---------------------------------------------------------------------------


def filter_activities_qs(qs: QuerySet, request: "HttpRequest") -> QuerySet:
    """
    Return *qs* filtered to activities the requesting user may see.

    An activity is visible when:
    - It has no parent record (customer/task/proposal-only) → always visible to
      any authenticated member of the firm.
    - Its parent record is visible according to ``filter_records_qs``.

    Additionally, ``visibility='restricted'`` activities are only visible to:
    - The activity author (``activity.user == request.user``).
    - Users whose effective scope for the parent record is ``team`` or ``all``.
    """
    membership: "Membership | None" = getattr(request, "membership", None)
    if membership is None:
        return qs.none()

    if membership.is_owner:
        return qs

    user = request.user

    # For activities linked to a record, apply record-level scoping.
    from crm.models import PipelineRecord  # noqa: PLC0415

    visible_record_ids = filter_records_qs(
        PipelineRecord.objects.filter(firm=request.firm),
        request,
    ).values_list("id", flat=True)

    # Determine whether this user has wide enough scope to see restricted activities.
    scope = resolve_scope(membership, Permission.RECORD_VIEW)
    user_sees_restricted = scope in (Scope.TEAM, Scope.ALL)

    # Base filter: only activities whose parent record is visible.
    record_filter = Q(record_id__isnull=True) | Q(record_id__in=visible_record_ids)

    if user_sees_restricted:
        # Wide scope – no additional restriction on visibility field.
        return qs.filter(record_filter)

    # Narrow scope (own / category): restricted activities are only visible if
    # the requesting user is the author.
    return qs.filter(record_filter).filter(
        Q(visibility="public") | Q(user=user)
    )


# ---------------------------------------------------------------------------
# filter_proposals_qs
# ---------------------------------------------------------------------------


def filter_proposals_qs(qs: QuerySet, request: "HttpRequest") -> QuerySet:
    """
    Return *qs* filtered to proposals the requesting user may see.

    Proposals are accessible when:
    - The user has ``proposal.create`` permission AND their scope allows the
      parent record (if any), OR
    - The proposal is directly created by / assigned to the user.
    """
    membership: "Membership | None" = getattr(request, "membership", None)
    if membership is None:
        return qs.none()

    if membership.is_owner:
        return qs

    user = request.user
    scope = resolve_scope(membership, Permission.PROPOSAL_CREATE)

    if scope == Scope.ALL:
        return qs

    # For proposals linked to a record, apply record-level scoping.
    from crm.models import PipelineRecord  # noqa: PLC0415

    visible_record_ids = filter_records_qs(
        PipelineRecord.objects.filter(firm=request.firm),
        request,
    ).values_list("id", flat=True)

    return qs.filter(
        Q(record_id__isnull=True, created_by=user)
        | Q(record_id__isnull=True, assigned_to=user)
        | Q(record_id__in=visible_record_ids)
    )


# ---------------------------------------------------------------------------
# filter_tasks_qs
# ---------------------------------------------------------------------------


def filter_tasks_qs(qs: QuerySet, request: "HttpRequest") -> QuerySet:
    """
    Return *qs* filtered to tasks the requesting user may see.

    A task is visible when:
    - It is assigned to or created by the user, OR
    - It is linked to a record the user can see.
    """
    membership: "Membership | None" = getattr(request, "membership", None)
    if membership is None:
        return qs.none()

    if membership.is_owner:
        return qs

    user = request.user
    scope = resolve_scope(membership, Permission.RECORD_VIEW)

    if scope == Scope.ALL:
        return qs

    from crm.models import PipelineRecord  # noqa: PLC0415

    visible_record_ids = filter_records_qs(
        PipelineRecord.objects.filter(firm=request.firm),
        request,
    ).values_list("id", flat=True)

    return qs.filter(
        Q(created_by=user)
        | Q(assigned_to=user)
        | Q(record_id__in=visible_record_ids)
    )
