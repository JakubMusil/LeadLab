import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone as django_timezone


class UserManager(BaseUserManager):
    """Custom manager that uses email instead of username."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with email as the primary identifier.

    Fields beyond the standard AbstractBaseUser:
        - timezone:        IANA timezone string used for display formatting.
        - profile_picture: Optional avatar image stored in MEDIA_ROOT/profiles/.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA timezone string, e.g. 'Europe/Prague'.",
    )
    profile_picture = models.ImageField(
        upload_to="profiles/", null=True, blank=True
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=django_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["email"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class UserStreamlinePreference(models.Model):
    """
    Per-user preferences for the Streamline (activity timeline) UI.

    Stores which activity types the user has explicitly hidden in the
    timeline filter dropdown.  We persist *hidden* types (rather than
    visible ones) so that newly registered ``StreamlineTool`` types are
    automatically shown or hidden according to their built-in
    ``default_visibility``, without requiring every user to revisit their
    preferences.

    Field
    -----
    hidden_activity_types : list[str]
        Activity type identifiers (e.g. ``"system_note"``, ``"tag_added"``)
        the user has chosen to hide.  An empty list means "use the
        per-tool defaults".
    """

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="streamline_preference",
        primary_key=True,
    )
    hidden_activity_types = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "user streamline preference"
        verbose_name_plural = "user streamline preferences"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"StreamlinePref({self.user_id})"
