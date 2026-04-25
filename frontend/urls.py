from django.urls import path

from frontend import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("dashboard/", views.dashboard_index, name="dashboard"),
    path("dashboard/leads/", views.dashboard_leads, name="dashboard-leads"),
    path("dashboard/customers/", views.dashboard_customers, name="dashboard-customers"),
    path("dashboard/calendar/", views.dashboard_calendar, name="dashboard-calendar"),
    path("dashboard/team/", views.dashboard_team, name="dashboard-team"),
    path("dashboard/settings/", views.dashboard_settings, name="dashboard-settings"),
]
