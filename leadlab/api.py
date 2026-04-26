"""
Central Django Ninja API instance for LeadLab.

All routers are registered here and mounted at /api/v1/.
"""
from ninja import NinjaAPI
from ninja.security import django_auth

from crm.api import router as crm_router
from crm.integrations_api import router as integrations_router
from crm.proposals_api import proposals_router
from crm.push_api import router as push_router
from firms.api import router as firms_router
from firms.billing_api import billing_router
from firms.invitations_api import public_router as public_invitations_router
from firms.stripe_webhook import webhook_router
from firms.token_auth import BearerTokenAuth
from firms.tokens_api import router as tokens_router
from firms.webhooks_api import router as webhooks_router
from firms.plugins_api import router as plugins_router
from leadlab.health import health_router
from users.api import router as users_router

api = NinjaAPI(
    title="LeadLab API",
    version="2.4.0",
    description="Multi-tenant SaaS CRM — REST API",
    auth=[django_auth, BearerTokenAuth()],
    urls_namespace="api",
)

api.add_router("/users/", users_router)
api.add_router("/firms/", firms_router)
api.add_router("/firms/", billing_router)
api.add_router("/firms/", tokens_router)
api.add_router("/firms/", webhooks_router)
api.add_router("/invitations/", public_invitations_router)
api.add_router("/crm/", crm_router)
api.add_router("/crm/", proposals_router)
api.add_router("/integrations/", integrations_router)
api.add_router("/push/", push_router)
api.add_router("/stripe/", webhook_router)
api.add_router("/plugins/", plugins_router)
api.add_router("/health/", health_router)
