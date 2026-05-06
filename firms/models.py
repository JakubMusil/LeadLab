import hashlib
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone as django_timezone
from django.utils.text import slugify

_logger = logging.getLogger(__name__)


class Firm(models.Model):
    """
    Top-level tenancy boundary. Every piece of CRM data belongs to exactly
    one Firm; users can be members of multiple Firms.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Stripe integration
    stripe_customer_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    subscription_tier = models.CharField(
        max_length=20,
        choices=[("free", "Free"), ("pro", "Pro")],
        default="free",
    )
    subscription_active = models.BooleanField(default=True)
    logo = models.ImageField(upload_to='firm_logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, blank=True, default='#dc2626')

    # Currency & formatting settings
    default_currency = models.CharField(
        max_length=3,
        default="CZK",
        help_text="ISO 4217 currency code used as the reporting currency for this workspace.",
    )
    number_locale = models.CharField(
        max_length=10,
        default="cs-CZ",
        help_text="BCP 47 locale tag controlling number/currency formatting (e.g. 'cs-CZ', 'en-US').",
    )
    exchange_rate_mode = models.CharField(
        max_length=10,
        choices=[("auto", "Automatic (ECB)"), ("manual", "Manual rates")],
        default="auto",
        help_text="How exchange rates are sourced for this workspace.",
    )

    class Meta:
        verbose_name = "firm"
        verbose_name_plural = "firms"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Firm.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class MembershipRole(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    # Deprecated alias kept for backward compatibility; new code should use MEMBER.
    WORKER = "worker", "Worker"


# ---------------------------------------------------------------------------
# Phase 2 – Permission catalogue, Role, Team
# ---------------------------------------------------------------------------


class PermissionRecord(models.Model):
    """
    Catalogue of all action × resource permission codes.
    Seeded by a data migration; the table is effectively read-only in
    production (managed only by Django migrations).
    """

    code = models.CharField(
        primary_key=True,
        max_length=60,
        help_text="Dot-notation permission code, e.g. 'record.edit'.",
    )
    group = models.CharField(
        max_length=40,
        db_index=True,
        help_text="Logical group shown in the permissions UI (e.g. 'Records', 'Billing').",
    )
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "permission"
        verbose_name_plural = "permissions"
        ordering = ["group", "code"]

    def __str__(self):
        return self.code


class Role(models.Model):
    """Per-firm role definition.  System roles are pre-created for every Firm."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="roles",
    )
    code = models.CharField(
        max_length=60,
        help_text="Short identifier, e.g. 'member', 'sales-lead'.  Unique within firm.",
    )
    name = models.CharField(max_length=100)
    is_system = models.BooleanField(
        default=False,
        help_text="System roles are pre-created per firm and cannot be deleted.",
    )
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    permissions = models.ManyToManyField(
        PermissionRecord,
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        verbose_name = "role"
        verbose_name_plural = "roles"
        unique_together = [("firm", "code")]
        ordering = ["firm", "name"]

    def __str__(self):
        return f"{self.name} ({self.firm})"


class RolePermission(models.Model):
    """M2M through-table: Role ↔ PermissionRecord."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        PermissionRecord,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )

    class Meta:
        unique_together = [("role", "permission")]

    def __str__(self):
        return f"{self.role.code} → {self.permission_id}"


class Team(models.Model):
    """Group of members within a firm (single-level, no nested teams)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True)
    color = models.CharField(
        max_length=7,
        blank=True,
        default="#6366f1",
        help_text="Hex colour used in the UI, e.g. '#6366f1'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "team"
        verbose_name_plural = "teams"
        unique_together = [("firm", "slug")]
        ordering = ["firm", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            candidate = base_slug
            counter = 1
            while Team.objects.filter(firm=self.firm, slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.firm})"


# ---------------------------------------------------------------------------
# MembershipManager – handles legacy ``role=`` kwarg transparently
# ---------------------------------------------------------------------------

class MembershipManager(models.Manager):
    """Custom manager that intercepts the deprecated ``role=`` keyword argument.

    Callers may still pass ``role='owner'`` (or a ``MembershipRole`` value) to
    ``create()`` / ``get_or_create()``.  The manager strips the kwarg from the
    SQL INSERT (the column no longer exists) and, after the row is persisted,
    calls ``_assign_system_role_by_code()`` to maintain the M2M ``roles``
    relation.
    """

    def create(self, **kwargs):
        role = kwargs.pop("role", None)
        obj = super().create(**kwargs)
        if role is not None:
            try:
                obj._assign_system_role_by_code(str(role))
            except Exception as exc:  # noqa: BLE001 – degrade gracefully; never block the create
                _logger.warning(
                    "MembershipManager.create: failed to assign system role '%s' to %s: %s",
                    role,
                    obj.pk,
                    exc,
                )
        return obj


class Membership(models.Model):
    """
    Relates a User to a Firm via M2M ``roles``.

    Business rules:
        - Each Firm has exactly one Owner (enforced at application level).
        - Only the Owner can delete the Firm.
        - Admin can invite/remove members.
        - Member has read/write access to CRM data but cannot manage billing or team.

    The legacy ``role`` CharField was removed in v2.2.  Use ``roles`` (M2M to
    ``Role``) and the ``primary_role`` property for all role-related logic.
    ``MembershipManager.create()`` transparently handles any ``role=`` kwarg
    still present in tests and legacy call-sites by mapping it to the matching
    system ``Role`` via M2M.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    # v2.2: legacy ``role`` CharField removed – M2M ``roles`` is now authoritative.
    # Phase 2 – granular role assignments.
    roles = models.ManyToManyField(
        Role,
        related_name="memberships",
        blank=True,
        verbose_name="Roles",
    )
    # Default scope controls which records a member sees when no finer-grained
    # grant is present.  Effective in Phase 4 (PERMISSIONS_V2_ENABLED=True).
    default_scope = models.CharField(
        max_length=20,
        choices=[
            ("own", "Own (created by or assigned to me)"),
            ("team", "Team (my team's records)"),
            ("category", "Category (specific categories)"),
            ("all", "All records in workspace"),
        ],
        default="own",
    )
    # Optional primary team assignment – used for scope=team resolution.
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_memberships",
    )
    weekly_digest_enabled = models.BooleanField(
        default=True,
        help_text="Receive a weekly email digest with pipeline summary for this workspace.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MembershipManager()

    class Meta:
        verbose_name = "membership"
        verbose_name_plural = "memberships"
        unique_together = [("user", "firm")]
        ordering = ["firm", "created_at"]

    def __str__(self):
        return f"{self.user} – {self.firm} ({self.primary_role})"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_owner(self):
        return self.primary_role == "owner"

    @property
    def is_admin_or_above(self):
        return self.primary_role in ("owner", "admin")

    @property
    def primary_role(self) -> str:
        """Return the highest-priority role *code* derived from the M2M ``roles``
        relation.

        Priority order (highest wins): owner → admin → member → worker → guest → other.
        Returns ``'guest'`` as the most restrictive fallback when no roles are
        assigned (this should not happen in a correctly initialised workspace).
        """
        _priority = {"owner": 0, "admin": 1, "member": 2, "worker": 3, "guest": 4}
        try:
            codes = list(self.roles.values_list("code", flat=True))
        except Exception:
            codes = []
        if codes:
            return min(codes, key=lambda c: _priority.get(c, 99))
        return "guest"

    def _assign_system_role_by_code(self, role_code: str) -> None:
        """Assign the system Role matching *role_code* to this membership via M2M.

        Replaces any previously assigned *system* roles so there is exactly one
        system role active at a time.  Custom (non-system) roles are preserved.

        This is the canonical write path used by all code that previously wrote
        to the legacy ``role`` CharField.
        """
        from firms.role_seeds import LEGACY_TO_SYSTEM_ROLE  # avoid circular at module level
        # Normalise: e.g. 'worker' → 'member'
        system_code = LEGACY_TO_SYSTEM_ROLE.get(str(role_code), str(role_code))
        try:
            system_role = Role.objects.get(
                firm_id=self.firm_id,
                code=system_code,
                is_system=True,
            )
        except Role.DoesNotExist:
            return  # System roles not yet seeded (e.g. fresh test DB without seed)

        current_system_roles = list(self.roles.filter(is_system=True))
        if len(current_system_roles) == 1 and current_system_roles[0].pk == system_role.pk:
            return  # Already correct – nothing to do.

        self.roles.remove(*[r for r in current_system_roles if r.pk != system_role.pk])
        self.roles.add(system_role)


class TeamMembership(models.Model):
    """M2M through-table: Team ↔ Membership.

    Allows a single Membership to participate in multiple Teams while the
    ``Membership.team`` FK captures the *primary* team for scope resolution.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team_memberships")
    membership = models.ForeignKey(
        Membership,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("team", "membership")]

    def __str__(self):
        return f"{self.membership} in {self.team}"


# ---------------------------------------------------------------------------
# Phase 3 – Permission Audit Log
# ---------------------------------------------------------------------------


class PermissionAuditLog(models.Model):
    """
    Append-only audit trail for all permission-related changes.

    Created automatically by post_save / post_delete signals on:
    ``Role``, ``Membership``, ``CategoryGrant``, ``RecordGrant``.

    The log is intentionally append-only – update and delete operations are
    prohibited at the application level (the admin shows it as readonly).
    ``target_type`` / ``target_id`` use a simple string tag so no GenericFK
    dependency is needed.
    """

    ACTION_CHOICES = [
        ("role.created", "Role created"),
        ("role.updated", "Role updated"),
        ("role.deleted", "Role deleted"),
        ("membership.created", "Membership created"),
        ("membership.updated", "Membership updated"),
        ("membership.deleted", "Membership deleted"),
        ("category_grant.created", "CategoryGrant created"),
        ("category_grant.deleted", "CategoryGrant deleted"),
        ("record_grant.created", "RecordGrant created"),
        ("record_grant.deleted", "RecordGrant deleted"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="permission_audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="permission_audit_logs",
        help_text="The user who performed the action. Null for system/migration actions.",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    target_type = models.CharField(
        max_length=40,
        db_index=True,
        help_text="Type tag of the affected object (e.g. 'role', 'membership').",
    )
    target_id = models.CharField(
        max_length=40,
        db_index=True,
        help_text="String representation of the affected object's PK.",
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of changed fields or relevant context.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "permission audit log"
        verbose_name_plural = "permission audit logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["firm", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.target_type}#{self.target_id} by {self.actor}"


_INVITATION_EXPIRY_DAYS = 7


def _default_expiry():
    return django_timezone.now() + timedelta(days=_INVITATION_EXPIRY_DAYS)


class Invitation(models.Model):
    """
    A pending invitation for a user (who may not yet have an account) to join a Firm.

    Lifecycle:
        1. An Admin/Owner calls ``POST /firms/{id}/invitations`` — creates this record.
        2. An email is dispatched (async) containing ``/invitations/{token}/accept``.
        3. The recipient opens the link:
           - If they already have an account they authenticate and are added as a Member.
           - If they do not have an account they provide a password to register, then join.
        4. ``accepted_at`` is set and the Membership is created atomically.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    email = models.EmailField()
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.WORKER,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)

    # Phase 6 – extended invite settings applied to Membership on accept.
    # ``role_codes`` stores a JSON list of Role.code strings so the invite can
    # pre-assign granular roles without needing a FK to Role (roles may not
    # exist on the accepting side yet if DB is recreated from invitation data).
    invited_role_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Role.code strings to assign to the Membership on accept.",
    )
    invited_default_scope = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Default scope to apply to the Membership on accept (own/team/category/all).",
    )
    invited_team = models.ForeignKey(
        "Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_invitations",
        help_text="Team to assign the invitee to on accept.",
    )

    class Meta:
        verbose_name = "invitation"
        verbose_name_plural = "invitations"
        unique_together = [("email", "firm")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invitation({self.email} → {self.firm})"

    @property
    def is_expired(self):
        return django_timezone.now() > self.expires_at

    @property
    def is_accepted(self):
        return self.accepted_at is not None


# ---------------------------------------------------------------------------
# API Token
# ---------------------------------------------------------------------------

_TOKEN_PREFIX_LENGTH = 8
_TOKEN_SECRET_BYTES = 32


def _generate_token() -> tuple[str, str, str]:
    """
    Generate a new API token.

    Returns:
        (plain_token, prefix, token_hash)

    The plain_token is shown to the user exactly once; only the hash is
    stored in the database.
    """
    raw = secrets.token_urlsafe(_TOKEN_SECRET_BYTES)
    prefix = raw[:_TOKEN_PREFIX_LENGTH]
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, token_hash


class APIToken(models.Model):
    """
    A long-lived bearer token that grants API access on behalf of a
    specific User within a specific Firm.

    The raw token value is shown once at creation time; only a SHA-256 hash
    is persisted so that a database breach cannot be used to authenticate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    name = models.CharField(max_length=100, help_text="A human-readable label for this token.")
    prefix = models.CharField(
        max_length=_TOKEN_PREFIX_LENGTH,
        help_text="First few characters of the token, shown in listings.",
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA-256 hash of the raw token value.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API token"
        verbose_name_plural = "API tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["firm", "user"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.prefix}…) — {self.firm}"

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and django_timezone.now() > self.expires_at:
            return False
        return True

    @classmethod
    def create_for_user(cls, firm: "Firm", user, name: str) -> tuple["APIToken", str]:
        """
        Create a new token and return ``(token_instance, plain_text)``.

        The plain text is returned only here and is not stored anywhere.
        """
        raw, prefix, token_hash = _generate_token()
        token = cls.objects.create(
            firm=firm,
            user=user,
            name=name,
            prefix=prefix,
            token_hash=token_hash,
        )
        return token, raw

    @classmethod
    def authenticate(cls, raw_token: str) -> "APIToken | None":
        """
        Look up an active token by its raw value.  Updates ``last_used_at``
        on success.  Returns ``None`` if the token is unknown or inactive.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        try:
            token = cls.objects.select_related("user", "firm").get(
                token_hash=token_hash,
                revoked_at__isnull=True,
            )
        except cls.DoesNotExist:
            return None
        if not token.is_active:
            return None
        # Update last_used_at without touching other fields.
        cls.objects.filter(pk=token.pk).update(last_used_at=django_timezone.now())
        return token


# ---------------------------------------------------------------------------
# Webhook Endpoint & Delivery Log
# ---------------------------------------------------------------------------


class PluginConfig(models.Model):
    """
    Per-firm storage for a single plugin's configuration values and
    enabled/disabled status.

    ``config`` holds arbitrary JSON matching the plugin's ``config_schema``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="plugin_configs",
    )
    plugin_name = models.CharField(
        max_length=100,
        help_text="Matches LeadLabPlugin.manifest['name'].",
    )
    enabled = models.BooleanField(default=True)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Plugin-specific configuration values (validated by plugin's config_schema).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plugin config"
        verbose_name_plural = "plugin configs"
        unique_together = [("firm", "plugin_name")]
        ordering = ["plugin_name"]

    def __str__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"{self.plugin_name} ({status}) — {self.firm}"


class WebhookEndpoint(models.Model):
    """
    A user-configured HTTP endpoint that receives signed POST requests when
    specific CRM events occur within the Firm.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
    )
    url = models.URLField(max_length=500, help_text="The URL that will receive POST requests.")
    secret = models.CharField(
        max_length=64,
        help_text="HMAC signing secret — sent as X-LeadLab-Signature.",
        default=secrets.token_hex,
    )
    events = models.JSONField(
        default=list,
        help_text="List of event names to subscribe to, e.g. ['record.created', 'activity.created']. "
                  "Empty list means all events.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "webhook endpoint"
        verbose_name_plural = "webhook endpoints"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.url} ({'active' if self.is_active else 'inactive'})"

    def subscribes_to(self, event: str) -> bool:
        """Return True if this endpoint should receive *event*."""
        return not self.events or event in self.events


class WebhookDelivery(models.Model):
    """
    An immutable log entry for a single webhook delivery attempt.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event = models.CharField(max_length=100)
    payload = models.JSONField()
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error = models.TextField(blank=True)
    delivered_at = models.DateTimeField(auto_now_add=True)
    duration_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False)

    class Meta:
        verbose_name = "webhook delivery"
        verbose_name_plural = "webhook deliveries"
        ordering = ["-delivered_at"]
        indexes = [
            models.Index(fields=["endpoint", "-delivered_at"]),
        ]

    def __str__(self):
        ok = "✓" if self.success else "✗"
        return f"{ok} {self.event} → {self.endpoint.url}"


# ---------------------------------------------------------------------------
# Exchange Rate Engine
# ---------------------------------------------------------------------------


class SystemExchangeRate(models.Model):
    """
    Global exchange rates fetched from ECB. Not scoped to a firm.
    Used when firm.exchange_rate_mode == 'auto' and no firm-level override exists.
    Base currency is always EUR (ECB publishes EUR-based rates).
    """

    base_currency = models.CharField(max_length=3, default="EUR")
    quote_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    date = models.DateField()
    source = models.CharField(max_length=20, default="ecb")

    class Meta:
        verbose_name = "system exchange rate"
        verbose_name_plural = "system exchange rates"
        unique_together = [("base_currency", "quote_currency", "date")]
        indexes = [
            models.Index(fields=["quote_currency", "-date"]),
            models.Index(fields=["base_currency", "-date"]),
        ]

    def __str__(self):
        return f"{self.base_currency}/{self.quote_currency} = {self.rate} ({self.date})"


class FirmExchangeRate(models.Model):
    """
    Exchange rate for a specific currency pair, scoped to a Firm.

    Priority logic:
    - If firm.exchange_rate_mode == 'manual': only manual rates are used.
    - If firm.exchange_rate_mode == 'auto': system-wide ECB rates are used,
      but a firm-level manual override takes precedence for a given pair.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(
        Firm,
        on_delete=models.CASCADE,
        related_name="exchange_rates",
    )
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=8)

    source = models.CharField(
        max_length=10,
        choices=[("manual", "Manual"), ("ecb", "ECB Auto")],
        default="manual",
    )
    valid_from = models.DateField(
        help_text="Rate is effective from this date (inclusive)."
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        help_text="Rate is effective until this date (inclusive). NULL = currently active.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User who created this rate (NULL for system/ECB rates).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    note = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional note visible to team members.",
    )

    class Meta:
        verbose_name = "firm exchange rate"
        verbose_name_plural = "firm exchange rates"
        ordering = ["-valid_from"]
        indexes = [
            models.Index(fields=["firm", "from_currency", "to_currency", "-valid_from"]),
        ]

    def __str__(self):
        return f"{self.from_currency}→{self.to_currency} @ {self.rate} ({self.valid_from})"
