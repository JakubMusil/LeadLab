from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


def landing(request):
    return render(request, "frontend/landing.html")


def login_view(request):
    return render(request, "frontend/login.html")


def register_view(request):
    return render(request, "frontend/register.html")


def logout_redirect(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("/login/")


def forgot_password(request):
    return render(request, "frontend/forgot_password.html")


def reset_password(request, uidb64, token):
    return render(request, "frontend/reset_password.html", {"uidb64": uidb64, "token": token})


def accept_invite(request, token):
    return render(request, "frontend/accept_invite.html", {"token": token})


@login_required(login_url="/login/")
def onboarding(request):
    return render(request, "frontend/onboarding.html")


@login_required(login_url="/login/")
def dashboard_index(request):
    return render(request, "frontend/dashboard/index.html")


@login_required(login_url="/login/")
def dashboard_leads(request):
    return render(request, "frontend/dashboard/leads.html")


@login_required(login_url="/login/")
def dashboard_customers(request):
    return render(request, "frontend/dashboard/customers.html")


@login_required(login_url="/login/")
def dashboard_calendar(request):
    return render(request, "frontend/dashboard/calendar.html")


@login_required(login_url="/login/")
def dashboard_team(request):
    return render(request, "frontend/dashboard/team.html")


@login_required(login_url="/login/")
def dashboard_settings(request):
    return render(request, "frontend/dashboard/settings.html")


@login_required(login_url="/login/")
def lead_detail(request, lead_id):
    return render(request, "frontend/dashboard/lead_detail.html", {"lead_id": lead_id})


@login_required(login_url="/login/")
def customer_detail(request, customer_id):
    return render(request, "frontend/dashboard/customer_detail.html", {"customer_id": customer_id})
