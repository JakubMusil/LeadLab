"""
Django Ninja API router – Users & Authentication
"""
from typing import List, Optional

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from ninja import File, Router, Schema, UploadedFile
from ninja.security import django_auth

from users.models import User, UserStreamlinePreference
from users.throttle import rate_limit

router = Router(tags=["users"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserOut(Schema):
    id: str
    email: str
    first_name: str
    last_name: str
    timezone: str
    full_name: str
    is_staff: bool = False
    is_superuser: bool = False


class RegisterIn(Schema):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""
    timezone: str = "UTC"


class LoginIn(Schema):
    email: str
    password: str


class ProfileUpdateIn(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None


class PasswordResetRequestIn(Schema):
    email: str


class PasswordResetConfirmIn(Schema):
    uid: str
    token: str
    new_password: str


class ErrorOut(Schema):
    detail: str


class StreamlinePreferenceIn(Schema):
    hidden_activity_types: List[str]


class StreamlinePreferenceOut(Schema):
    hidden_activity_types: List[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", auth=None, response={201: UserOut, 400: ErrorOut})
@rate_limit("register", limit=10, window=60)
def register(request, payload: RegisterIn):
    """Create a new user account."""
    if User.objects.filter(email=payload.email).exists():
        return 400, {"detail": "A user with that email already exists."}

    user = User.objects.create_user(
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        timezone=payload.timezone,
    )
    return 201, _user_out(user)


@router.post("/login", auth=None, response={200: UserOut, 401: ErrorOut})
@rate_limit("login", limit=5, window=60)
def login_view(request, payload: LoginIn):
    """Authenticate and start a session."""
    user = authenticate(request, username=payload.email, password=payload.password)
    if user is None:
        return 401, {"detail": "Invalid credentials."}
    login(request, user)
    return 200, _user_out(user)


@router.post("/logout", auth=django_auth, response={200: dict})
def logout_view(request):
    """End the current session."""
    logout(request)
    return 200, {"detail": "Logged out successfully."}


@router.get("/me", auth=django_auth, response={200: UserOut, 401: ErrorOut})
def me(request):
    """Return the currently authenticated user."""
    return 200, _user_out(request.user)


@router.patch("/me", auth=django_auth, response={200: UserOut, 400: ErrorOut})
def update_profile(request, payload: ProfileUpdateIn):
    """Update the current user's profile (first_name, last_name, timezone)."""
    user = request.user
    updated = False
    if payload.first_name is not None:
        user.first_name = payload.first_name
        updated = True
    if payload.last_name is not None:
        user.last_name = payload.last_name
        updated = True
    if payload.timezone is not None:
        user.timezone = payload.timezone
        updated = True
    if updated:
        user.save()
    return 200, _user_out(user)


@router.post("/me/avatar", auth=django_auth, response={200: UserOut, 400: ErrorOut})
def upload_avatar(request, avatar: UploadedFile = File(...)):
    """Upload or replace the current user's profile picture."""
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if avatar.content_type not in allowed_types:
        return 400, {"detail": "Unsupported file type. Allowed: jpeg, png, gif, webp."}
    user = request.user
    # Delete the old file if one exists to avoid orphans on disk.
    if user.profile_picture:
        user.profile_picture.delete(save=False)
    user.profile_picture.save(avatar.name, avatar, save=True)
    return 200, _user_out(user)


@router.get(
    "/me/streamline-preferences",
    auth=django_auth,
    response={200: StreamlinePreferenceOut},
)
def get_streamline_preferences(request):
    """
    Return the current user's Streamline (activity timeline) filter
    preferences.

    The response contains the list of activity types the user has
    explicitly hidden.  The frontend combines this with each tool's
    built-in ``default_visibility`` to compute the effective filter.
    """
    pref, _created = UserStreamlinePreference.objects.get_or_create(user=request.user)
    return 200, {"hidden_activity_types": list(pref.hidden_activity_types or [])}


@router.put(
    "/me/streamline-preferences",
    auth=django_auth,
    response={200: StreamlinePreferenceOut, 400: ErrorOut},
)
def update_streamline_preferences(request, payload: StreamlinePreferenceIn):
    """
    Replace the current user's Streamline filter preferences.

    Accepts a list of activity type identifiers to hide.  Unknown types
    are kept as-is so a user's preferences survive a tool being
    temporarily unregistered (e.g. by a feature flag).
    """
    # Sanitize: drop empty strings and duplicates while preserving order.
    seen: set[str] = set()
    cleaned: list[str] = []
    for at in payload.hidden_activity_types:
        if not isinstance(at, str):
            return 400, {"detail": "hidden_activity_types must be a list of strings."}
        v = at.strip()
        if not v or v in seen:
            continue
        seen.add(v)
        cleaned.append(v)

    pref, _created = UserStreamlinePreference.objects.get_or_create(user=request.user)
    pref.hidden_activity_types = cleaned
    pref.save(update_fields=["hidden_activity_types", "updated_at"])
    return 200, {"hidden_activity_types": cleaned}


@router.post(
    "/password-reset/request",
    auth=None,
    response={200: dict},
)
@rate_limit("password_reset", limit=5, window=60)
def password_reset_request(request, payload: PasswordResetRequestIn):
    """
    Request a password-reset email.

    Always returns 200 to avoid revealing whether the email address is
    registered.  The email is dispatched asynchronously via Celery.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from users.tasks import send_password_reset_email

    user = User.objects.filter(email=payload.email).first()
    if user is not None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        try:
            send_password_reset_email.delay(str(user.id), token, uid)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "password_reset_request: Could not enqueue send_password_reset_email "
                "for user %s (Celery may not be running).",
                user.id,
            )

    return 200, {"detail": "If that email is registered, a reset link has been sent."}


@router.post(
    "/password-reset/confirm",
    auth=None,
    response={200: dict, 400: ErrorOut},
)
def password_reset_confirm(request, payload: PasswordResetConfirmIn):
    """
    Set a new password using the uid and token from the reset email.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = force_str(urlsafe_base64_decode(payload.uid))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return 400, {"detail": "Invalid or expired password-reset link."}

    if not default_token_generator.check_token(user, payload.token):
        return 400, {"detail": "Invalid or expired password-reset link."}

    try:
        validate_password(payload.new_password, user)
    except ValidationError as exc:
        return 400, {"detail": " ".join(exc.messages)}

    user.set_password(payload.new_password)
    user.save()
    return 200, {"detail": "Password has been reset successfully."}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timezone": user.timezone,
        "full_name": user.full_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }
