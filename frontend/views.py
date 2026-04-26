import json
from pathlib import Path
from django.conf import settings
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


def _load_spa_assets():
    """Read the Vite manifest and return (js_url, css_urls) for the SPA entry point."""
    from django.templatetags.static import static

    manifest_path = (
        Path(settings.BASE_DIR) / 'frontend' / 'static' / 'frontend' / 'spa' / '.vite' / 'manifest.json'
    )
    try:
        manifest = json.loads(manifest_path.read_text())
        entry = manifest.get('index.html', {})
        js_file = entry.get('file', '')
        css_files = entry.get('css', [])
        js_url = static(f'frontend/spa/{js_file}') if js_file else None
        css_urls = [static(f'frontend/spa/{f}') for f in css_files]
        return js_url, css_urls
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None, []


def public_spa_shell(request, path=''):
    js_url, css_urls = _load_spa_assets()
    return render(request, 'frontend/spa_shell.html', {
        'spa_js_url': js_url,
        'spa_css_urls': css_urls,
    })


@login_required(login_url='/login/')
def spa_shell(request, path=''):
    js_url, css_urls = _load_spa_assets()
    return render(request, 'frontend/spa_shell.html', {
        'spa_js_url': js_url,
        'spa_css_urls': css_urls,
    })
