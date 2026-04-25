"""
Django Ninja API router – Users & Authentication
"""
from typing import Optional

from django.contrib.auth import authenticate, login, logout
from ninja import Router, Schema
from ninja.security import django_auth

from users.models import User

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


class RegisterIn(Schema):
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""
    timezone: str = "UTC"


class LoginIn(Schema):
    email: str
    password: str


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response={201: UserOut, 400: ErrorOut})
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
    return 201, {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timezone": user.timezone,
        "full_name": user.full_name,
    }


@router.post("/login", response={200: UserOut, 401: ErrorOut})
def login_view(request, payload: LoginIn):
    """Authenticate and start a session."""
    user = authenticate(request, username=payload.email, password=payload.password)
    if user is None:
        return 401, {"detail": "Invalid credentials."}
    login(request, user)
    return 200, {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timezone": user.timezone,
        "full_name": user.full_name,
    }


@router.post("/logout", auth=django_auth, response={200: dict})
def logout_view(request):
    """End the current session."""
    logout(request)
    return 200, {"detail": "Logged out successfully."}


@router.get("/me", auth=django_auth, response={200: UserOut, 401: ErrorOut})
def me(request):
    """Return the currently authenticated user."""
    u = request.user
    return 200, {
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "timezone": u.timezone,
        "full_name": u.full_name,
    }
