import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone as django_timezone
from django.utils.text import slugify


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
    WORKER = "worker", "Worker"


class Membership(models.Model):
    """
    Relates a User to a Firm with a specific role.

    Business rules:
        - Each Firm has exactly one Owner (enforced at application level).
        - Only the Owner can delete the Firm.
        - Admin can invite/remove Workers.
        - Worker has read/write access to CRM data but cannot manage billing or team.
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
    role = models.CharField(
        max_length=20,
        choices=MembershipRole.choices,
        default=MembershipRole.WORKER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membership"
        verbose_name_plural = "memberships"
        unique_together = [("user", "firm")]
        ordering = ["firm", "role"]

    def __str__(self):
        return f"{self.user} – {self.firm} ({self.get_role_display()})"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_owner(self):
        return self.role == MembershipRole.OWNER

    @property
    def is_admin_or_above(self):
        return self.role in (MembershipRole.OWNER, MembershipRole.ADMIN)


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
        help_text="List of event names to subscribe to, e.g. ['lead.created', 'activity.created']. "
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
