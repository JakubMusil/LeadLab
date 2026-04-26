from django.urls import path
from django.views.generic import RedirectView
from frontend import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_redirect, name="logout"),
    path("forgot-password/", views.forgot_password, name="forgot-password"),
    path("reset-password/<str:uidb64>/<str:token>/", views.reset_password, name="reset-password"),
    path("accept-invite/<str:token>/", views.accept_invite, name="accept-invite"),
    path("onboarding/", views.onboarding, name="onboarding"),
    # Legacy /dashboard/* routes — permanently redirect to the Vue SPA.
    path("dashboard/", RedirectView.as_view(url="/app/dashboard", permanent=True), name="dashboard"),
    path("dashboard/<path:rest>", RedirectView.as_view(url="/app/dashboard", permanent=True), name="dashboard-legacy"),
    # Vue 3 SPA shell — handles all /app/* routes.
    path("app/", views.spa_shell, name="spa-shell"),
    path("app/<path:path>", views.spa_shell, name="spa-shell-path"),
]
