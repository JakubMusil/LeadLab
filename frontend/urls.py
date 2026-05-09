from django.urls import path
from django.views.generic import RedirectView
from frontend import views

urlpatterns = [
    path("", views.public_spa_shell, name="landing"),
    path("login/", views.public_spa_shell, name="login"),
    path("register/", views.public_spa_shell, name="register"),
    path("logout/", views.logout_redirect, name="logout"),
    path("forgot-password/", views.public_spa_shell, name="forgot-password"),
    path("reset-password/<str:uidb64>/<str:token>/", views.public_spa_shell, name="reset-password"),
    path("accept-invite/<str:token>/", views.public_spa_shell, name="accept-invite"),
    path("onboarding/", views.public_spa_shell, name="onboarding"),
    # Legacy /dashboard/* routes — permanently redirect to the Vue SPA.
    path("dashboard/", RedirectView.as_view(url="/app/dashboard", permanent=True), name="dashboard"),
    path("dashboard/<path:rest>", RedirectView.as_view(url="/app/dashboard", permanent=True), name="dashboard-legacy"),
    # Vue 3 SPA shell — handles all /app/* routes.
    path("app/", views.public_spa_shell, name="spa-shell"),
    path("app/<path:path>", views.public_spa_shell, name="spa-shell-path"),
]
