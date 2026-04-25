from django.urls import path
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
    path("dashboard/", views.dashboard_index, name="dashboard"),
    path("dashboard/leads/", views.dashboard_leads, name="dashboard-leads"),
    path("dashboard/leads/<str:lead_id>/", views.lead_detail, name="lead-detail"),
    path("dashboard/customers/", views.dashboard_customers, name="dashboard-customers"),
    path("dashboard/customers/<str:customer_id>/", views.customer_detail, name="customer-detail"),
    path("dashboard/calendar/", views.dashboard_calendar, name="dashboard-calendar"),
    path("dashboard/team/", views.dashboard_team, name="dashboard-team"),
    path("dashboard/settings/", views.dashboard_settings, name="dashboard-settings"),
]
