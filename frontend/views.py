from django.shortcuts import render


def landing(request):
    return render(request, "frontend/landing.html")


def login_view(request):
    return render(request, "frontend/login.html")


def register_view(request):
    return render(request, "frontend/register.html")


def dashboard_index(request):
    return render(request, "frontend/dashboard/index.html")


def dashboard_leads(request):
    return render(request, "frontend/dashboard/leads.html")


def dashboard_customers(request):
    return render(request, "frontend/dashboard/customers.html")


def dashboard_calendar(request):
    return render(request, "frontend/dashboard/calendar.html")


def dashboard_team(request):
    return render(request, "frontend/dashboard/team.html")


def dashboard_settings(request):
    return render(request, "frontend/dashboard/settings.html")
