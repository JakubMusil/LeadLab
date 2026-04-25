"""
Central Django Ninja API instance for LeadLab.

All routers are registered here and mounted at /api/v1/.
"""
from ninja import NinjaAPI
from ninja.security import django_auth

from crm.api import router as crm_router
from firms.api import router as firms_router
from firms.billing_api import billing_router
from firms.invitations_api import public_router as public_invitations_router
from firms.stripe_webhook import webhook_router
from leadlab.health import health_router
from users.api import router as users_router

api = NinjaAPI(
    title="LeadLab API",
    version="1.0.0",
    description="Multi-tenant SaaS CRM — REST API",
    auth=django_auth,
    urls_namespace="api",
)

api.add_router("/users/", users_router)
api.add_router("/firms/", firms_router)
api.add_router("/firms/", billing_router)
api.add_router("/invitations/", public_invitations_router)
api.add_router("/crm/", crm_router)
api.add_router("/stripe/", webhook_router)
api.add_router("/health/", health_router)
