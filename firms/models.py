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
