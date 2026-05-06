import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory, override_settings

from firms.auth import (
    AuthenticationRequired,
    FirmNotFound,
    MembershipRole,
    PermissionDenied,
    SubscriptionRequired,
    check_tier_limits,
    require_active_subscription,
    require_membership,
    require_permission,
)
from firms.middleware import TenantMiddleware
from firms.models import Firm, Membership
from firms.permissions import Permission
from users.models import User


class FirmModelTest(TestCase):
    def test_slug_auto_generated(self):
        firm = Firm.objects.create(name="Acme Corp")
        self.assertEqual(firm.slug, "acme-corp")

    def test_slug_uniqueness(self):
        Firm.objects.create(name="Acme Corp")
        firm2 = Firm.objects.create(name="Acme Corp")
        self.assertEqual(firm2.slug, "acme-corp-1")

    def test_str(self):
        firm = Firm.objects.create(name="Test Firm")
        self.assertIn("Test Firm", str(firm))

    def test_default_tier(self):
        firm = Firm.objects.create(name="New Co")
        self.assertEqual(firm.subscription_tier, "free")
        self.assertTrue(firm.subscription_active)


class MembershipModelTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.com", password="pass")
        self.worker = User.objects.create_user(email="worker@example.com", password="pass")
        self.firm = Firm.objects.create(name="Test Firm")
        self.owner_membership = Membership.objects.create(
            user=self.owner, firm=self.firm, role=MembershipRole.OWNER
        )
        self.worker_membership = Membership.objects.create(
            user=self.worker, firm=self.firm, role=MembershipRole.WORKER
        )

    def test_is_owner_property(self):
        self.assertTrue(self.owner_membership.is_owner)
        self.assertFalse(self.worker_membership.is_owner)

    def test_is_admin_or_above(self):
        self.assertTrue(self.owner_membership.is_admin_or_above)
        admin = User.objects.create_user(email="admin@example.com", password="pass")
        admin_membership = Membership.objects.create(
            user=admin, firm=self.firm, role=MembershipRole.ADMIN
        )
        self.assertTrue(admin_membership.is_admin_or_above)
        self.assertFalse(self.worker_membership.is_admin_or_above)

    def test_unique_together(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Membership.objects.create(
                user=self.owner, firm=self.firm, role=MembershipRole.WORKER
            )


class TenantMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(email="user@example.com", password="pass")
        self.firm = Firm.objects.create(name="Middleware Firm")
        self.membership = Membership.objects.create(
            user=self.user, firm=self.firm, role=MembershipRole.WORKER
        )

    def _get_response(self, request):
        return None

    def test_firm_resolved_from_header(self):
        request = self.factory.get("/", HTTP_X_FIRM_ID=str(self.firm.id))
        request.user = self.user
        middleware = TenantMiddleware(self._get_response)
        middleware(request)
        self.assertIsNotNone(request.firm)
        self.assertEqual(request.firm.id, self.firm.id)

    def test_no_firm_header_sets_none(self):
        request = self.factory.get("/")
        request.user = self.user
        middleware = TenantMiddleware(self._get_response)
        middleware(request)
        self.assertIsNone(request.firm)

    def test_invalid_uuid_sets_none(self):
        request = self.factory.get("/", HTTP_X_FIRM_ID="not-a-uuid")
        request.user = self.user
        middleware = TenantMiddleware(self._get_response)
        middleware(request)
        self.assertIsNone(request.firm)

    def test_membership_resolved(self):
        request = self.factory.get("/", HTTP_X_FIRM_ID=str(self.firm.id))
        request.user = self.user
        middleware = TenantMiddleware(self._get_response)
        middleware(request)
        self.assertIsNotNone(request.membership)
        self.assertEqual(request.membership.role, MembershipRole.WORKER)


class FirmAuthTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(email="auth@example.com", password="pass")
        self.firm = Firm.objects.create(name="Auth Firm")
        self.membership = Membership.objects.create(
            user=self.user, firm=self.firm, role=MembershipRole.WORKER
        )

    def _make_request(self, firm=None, membership=None, authenticated=True):
        request = self.factory.get("/")
        request.user = self.user if authenticated else type("AnonUser", (), {"is_authenticated": False})()
        request.firm = firm
        request.membership = membership
        return request

    def test_require_membership_success(self):
        request = self._make_request(firm=self.firm, membership=self.membership)
        m = require_membership(request)
        self.assertEqual(m, self.membership)

    def test_require_membership_unauthenticated(self):
        request = self._make_request(authenticated=False)
        with self.assertRaises(AuthenticationRequired):
            require_membership(request)

    def test_require_membership_no_firm(self):
        request = self._make_request(firm=None)
        with self.assertRaises(FirmNotFound):
            require_membership(request)

    def test_require_membership_no_membership(self):
        request = self._make_request(firm=self.firm, membership=None)
        with self.assertRaises(PermissionDenied):
            require_membership(request)

    def test_require_membership_insufficient_role(self):
        request = self._make_request(firm=self.firm, membership=self.membership)
        with self.assertRaises(PermissionDenied):
            require_membership(request, min_role=MembershipRole.ADMIN)

    def test_require_active_subscription_passes(self):
        require_active_subscription(self.firm)  # no exception expected

    def test_require_active_subscription_fails(self):
        self.firm.subscription_active = False
        self.firm.save()
        with self.assertRaises(SubscriptionRequired):
            require_active_subscription(self.firm)

    def test_check_tier_limits_lead_count(self):
        from crm.models import PipelineRecord
        for i in range(50):
            PipelineRecord.objects.create(firm=self.firm, title=f"PipelineRecord {i}")
        with self.assertRaises(SubscriptionRequired):
            check_tier_limits(self.firm)

    def test_check_tier_limits_member_count(self):
        extra_user = User.objects.create_user(email="extra@example.com", password="pass")
        Membership.objects.create(user=extra_user, firm=self.firm, role=MembershipRole.WORKER)
        with self.assertRaises(SubscriptionRequired):
            check_tier_limits(self.firm)

    def test_check_tier_limits_pro_skips(self):
        self.firm.subscription_tier = "pro"
        self.firm.save()
        from crm.models import PipelineRecord
        for i in range(100):
            PipelineRecord.objects.create(firm=self.firm, title=f"PipelineRecord {i}")
        check_tier_limits(self.firm)  # no exception


# ---------------------------------------------------------------------------
# Firms API integration tests
# ---------------------------------------------------------------------------


class FirmsAPIFixtureMixin:
    """Sets up an owner user, a firm, and logs in via the test client."""

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@api.com", password="pass")
        self.worker = User.objects.create_user(email="worker@api.com", password="pass")
        self.firm = Firm.objects.create(name="API Firm", subscription_tier="pro")
        self.owner_membership = Membership.objects.create(
            user=self.owner, firm=self.firm, role=MembershipRole.OWNER
        )
        self.worker_membership = Membership.objects.create(
            user=self.worker, firm=self.firm, role=MembershipRole.WORKER
        )
        self.client.login(username="owner@api.com", password="pass")

    def firm_headers(self):
        return {"HTTP_X_FIRM_ID": str(self.firm.id)}

    def _post(self, url, data, **kwargs):
        return self.client.post(
            url, data=json.dumps(data), content_type="application/json", **kwargs
        )

    def _delete(self, url, **kwargs):
        return self.client.delete(url, content_type="application/json", **kwargs)


class ListFirmsAPITest(FirmsAPIFixtureMixin, TestCase):
    URL = "/api/v1/firms/"

    def test_list_firms_returns_own_firms(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        ids = [f["id"] for f in resp.json()]
        self.assertIn(str(self.firm.id), ids)

    def test_list_firms_unauthenticated_returns_error(self):
        self.client.logout()
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, [401, 403])


class CreateFirmAPITest(FirmsAPIFixtureMixin, TestCase):
    URL = "/api/v1/firms/"

    def test_create_firm_returns_201(self):
        resp = self._post(self.URL, {"name": "Brand New Firm"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["name"], "Brand New Firm")
        self.assertTrue(Firm.objects.filter(name="Brand New Firm").exists())

    def test_create_firm_makes_creator_owner(self):
        resp = self._post(self.URL, {"name": "Owned Firm"})
        self.assertEqual(resp.status_code, 201)
        firm = Firm.objects.get(name="Owned Firm")
        self.assertTrue(
            Membership.objects.filter(user=self.owner, firm=firm, role=MembershipRole.OWNER).exists()
        )


class GetFirmAPITest(FirmsAPIFixtureMixin, TestCase):
    def test_get_firm_returns_details(self):
        resp = self.client.get(f"/api/v1/firms/{self.firm.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "API Firm")

    def test_get_firm_non_member_returns_403(self):
        outsider = User.objects.create_user(email="outsider@api.com", password="pass")
        self.client.login(username="outsider@api.com", password="pass")
        resp = self.client.get(f"/api/v1/firms/{self.firm.id}")
        self.assertEqual(resp.status_code, 403)

    def test_get_nonexistent_firm_returns_404(self):
        resp = self.client.get(f"/api/v1/firms/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)


class DeleteFirmAPITest(FirmsAPIFixtureMixin, TestCase):
    def test_delete_firm_owner_succeeds(self):
        resp = self._delete(f"/api/v1/firms/{self.firm.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Firm.objects.filter(id=self.firm.id).exists())

    def test_delete_firm_worker_returns_403(self):
        self.client.login(username="worker@api.com", password="pass")
        resp = self._delete(f"/api/v1/firms/{self.firm.id}")
        self.assertEqual(resp.status_code, 403)


class ListMembersAPITest(FirmsAPIFixtureMixin, TestCase):
    def test_list_members_returns_all_members(self):
        resp = self.client.get(f"/api/v1/firms/{self.firm.id}/members")
        self.assertEqual(resp.status_code, 200)
        emails = [m["user_email"] for m in resp.json()]
        self.assertIn("owner@api.com", emails)
        self.assertIn("worker@api.com", emails)


class InviteMemberAPITest(FirmsAPIFixtureMixin, TestCase):
    URL_TPL = "/api/v1/firms/{firm_id}/members"

    def test_invite_existing_user_as_worker(self):
        new_user = User.objects.create_user(email="invite@api.com", password="pass")
        resp = self._post(
            self.URL_TPL.format(firm_id=self.firm.id),
            {"email": "invite@api.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Membership.objects.filter(user=new_user, firm=self.firm).exists())

    def test_invite_already_member_returns_400(self):
        resp = self._post(
            self.URL_TPL.format(firm_id=self.firm.id),
            {"email": "worker@api.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_invite_nonexistent_user_returns_400(self):
        resp = self._post(
            self.URL_TPL.format(firm_id=self.firm.id),
            {"email": "nobody@api.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_invite_worker_cannot_invite(self):
        new_user = User.objects.create_user(email="x@api.com", password="pass")
        self.client.login(username="worker@api.com", password="pass")
        resp = self._post(
            self.URL_TPL.format(firm_id=self.firm.id),
            {"email": "x@api.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 403)


class RemoveMemberAPITest(FirmsAPIFixtureMixin, TestCase):
    def test_remove_worker_succeeds(self):
        resp = self._delete(
            f"/api/v1/firms/{self.firm.id}/members/{self.worker_membership.id}"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Membership.objects.filter(id=self.worker_membership.id).exists())

    def test_remove_owner_returns_403(self):
        resp = self._delete(
            f"/api/v1/firms/{self.firm.id}/members/{self.owner_membership.id}"
        )
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Invitation model tests
# ---------------------------------------------------------------------------

from firms.models import Invitation


class InvitationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="owner@inv.com", password="pass")
        self.firm = Firm.objects.create(name="Inv Firm")

    def test_create_invitation(self):
        inv = Invitation.objects.create(
            email="invitee@example.com",
            firm=self.firm,
            role=MembershipRole.WORKER,
            invited_by=self.user,
        )
        self.assertIsNotNone(inv.token)
        self.assertFalse(inv.is_accepted)
        self.assertFalse(inv.is_expired)

    def test_str(self):
        inv = Invitation.objects.create(
            email="invitee@example.com",
            firm=self.firm,
        )
        self.assertIn("invitee@example.com", str(inv))
        self.assertIn("Inv Firm", str(inv))

    def test_is_accepted_property(self):
        from django.utils import timezone as tz
        inv = Invitation.objects.create(email="a@b.com", firm=self.firm)
        self.assertFalse(inv.is_accepted)
        inv.accepted_at = tz.now()
        inv.save()
        self.assertTrue(inv.is_accepted)

    def test_unique_together_email_firm(self):
        from django.db import IntegrityError
        Invitation.objects.create(email="dup@example.com", firm=self.firm)
        with self.assertRaises(IntegrityError):
            Invitation.objects.create(email="dup@example.com", firm=self.firm)

    def test_different_firms_same_email_allowed(self):
        firm2 = Firm.objects.create(name="Other Firm")
        Invitation.objects.create(email="shared@example.com", firm=self.firm)
        inv2 = Invitation.objects.create(email="shared@example.com", firm=firm2)
        self.assertIsNotNone(inv2.id)


# ---------------------------------------------------------------------------
# Invitation API tests
# ---------------------------------------------------------------------------

class InvitationAPIFixtureMixin(FirmsAPIFixtureMixin):
    INVITE_URL_TPL = "/api/v1/firms/{firm_id}/invitations/"
    PREVIEW_URL_TPL = "/api/v1/invitations/{token}"
    ACCEPT_URL_TPL = "/api/v1/invitations/{token}/accept"


class CreateInvitationAPITest(InvitationAPIFixtureMixin, TestCase):
    def test_owner_can_create_invitation(self):
        resp = self._post(
            self.INVITE_URL_TPL.format(firm_id=self.firm.id),
            {"email": "newperson@example.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["email"], "newperson@example.com")
        self.assertEqual(data["role"], "worker")
        self.assertIn("token", data)
        self.assertTrue(Invitation.objects.filter(email="newperson@example.com", firm=self.firm).exists())

    def test_worker_cannot_create_invitation(self):
        self.client.login(username="worker@api.com", password="pass")
        resp = self._post(
            self.INVITE_URL_TPL.format(firm_id=self.firm.id),
            {"email": "x@example.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_cannot_invite_owner_role(self):
        resp = self._post(
            self.INVITE_URL_TPL.format(firm_id=self.firm.id),
            {"email": "x@example.com", "role": "owner"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_cannot_invite_existing_member(self):
        resp = self._post(
            self.INVITE_URL_TPL.format(firm_id=self.firm.id),
            {"email": "worker@api.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_resend_refreshes_expiry(self):
        from datetime import timedelta
        from django.utils import timezone as tz
        # Create an expired invitation manually
        inv = Invitation.objects.create(
            email="expired@example.com",
            firm=self.firm,
            invited_by=self.owner,
            expires_at=tz.now() - timedelta(days=1),
        )
        resp = self._post(
            self.INVITE_URL_TPL.format(firm_id=self.firm.id),
            {"email": "expired@example.com", "role": "worker"},
        )
        self.assertEqual(resp.status_code, 202)
        inv.refresh_from_db()
        self.assertFalse(inv.is_expired)

    def test_unauthenticated_returns_error(self):
        self.client.logout()
        resp = self._post(
            self.INVITE_URL_TPL.format(firm_id=self.firm.id),
            {"email": "x@example.com", "role": "worker"},
        )
        self.assertIn(resp.status_code, [401, 403])


class PreviewInvitationAPITest(InvitationAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.invitation = Invitation.objects.create(
            email="preview@example.com",
            firm=self.firm,
            role=MembershipRole.WORKER,
            invited_by=self.owner,
        )

    def test_preview_valid_token(self):
        self.client.logout()
        resp = self.client.get(self.PREVIEW_URL_TPL.format(token=self.invitation.token))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["email"], "preview@example.com")
        self.assertEqual(data["firm_name"], "API Firm")
        self.assertFalse(data["is_expired"])
        self.assertFalse(data["is_accepted"])

    def test_preview_nonexistent_token_returns_404(self):
        self.client.logout()
        resp = self.client.get(self.PREVIEW_URL_TPL.format(token=uuid.uuid4()))
        self.assertEqual(resp.status_code, 404)

    def test_preview_expired_token_returns_410(self):
        from datetime import timedelta
        from django.utils import timezone as tz
        self.invitation.expires_at = tz.now() - timedelta(days=1)
        self.invitation.save()
        self.client.logout()
        resp = self.client.get(self.PREVIEW_URL_TPL.format(token=self.invitation.token))
        self.assertEqual(resp.status_code, 410)

    def test_preview_accepted_token_returns_410(self):
        from django.utils import timezone as tz
        self.invitation.accepted_at = tz.now()
        self.invitation.save()
        self.client.logout()
        resp = self.client.get(self.PREVIEW_URL_TPL.format(token=self.invitation.token))
        self.assertEqual(resp.status_code, 410)


class AcceptInvitationAPITest(InvitationAPIFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.invitation = Invitation.objects.create(
            email="acceptme@example.com",
            firm=self.firm,
            role=MembershipRole.WORKER,
            invited_by=self.owner,
        )

    def _accept(self, token, data):
        return self._post(self.ACCEPT_URL_TPL.format(token=token), data)

    def test_new_user_can_accept_and_gets_account(self):
        self.client.logout()
        resp = self._accept(
            self.invitation.token,
            {"password": "strongpassword123", "first_name": "New", "last_name": "User"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user_email"], "acceptme@example.com")
        self.assertEqual(data["role"], "worker")
        # Account created
        self.assertTrue(User.objects.filter(email="acceptme@example.com").exists())
        # Membership created
        new_user = User.objects.get(email="acceptme@example.com")
        self.assertTrue(Membership.objects.filter(user=new_user, firm=self.firm).exists())
        # Invitation stamped
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.accepted_at)

    def test_existing_user_can_accept(self):
        existing = User.objects.create_user(email="acceptme@example.com", password="mypassword")
        self.client.logout()
        resp = self._accept(
            self.invitation.token,
            {"password": "mypassword"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Membership.objects.filter(user=existing, firm=self.firm).exists())

    def test_wrong_password_for_existing_user_returns_400(self):
        User.objects.create_user(email="acceptme@example.com", password="correctpassword")
        self.client.logout()
        resp = self._accept(self.invitation.token, {"password": "wrongpassword"})
        self.assertEqual(resp.status_code, 400)

    def test_accept_expired_invitation_returns_410(self):
        from datetime import timedelta
        from django.utils import timezone as tz
        self.invitation.expires_at = tz.now() - timedelta(days=1)
        self.invitation.save()
        self.client.logout()
        resp = self._accept(self.invitation.token, {"password": "pass"})
        self.assertEqual(resp.status_code, 410)

    def test_accept_already_accepted_returns_410(self):
        from django.utils import timezone as tz
        self.invitation.accepted_at = tz.now()
        self.invitation.save()
        self.client.logout()
        resp = self._accept(self.invitation.token, {"password": "pass"})
        self.assertEqual(resp.status_code, 410)

    def test_accept_nonexistent_token_returns_404(self):
        self.client.logout()
        resp = self._accept(uuid.uuid4(), {"password": "pass"})
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Billing API tests
# ---------------------------------------------------------------------------

_STRIPE_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_fake",
    "STRIPE_PRICE_ID": "price_fake",
    "STRIPE_WEBHOOK_SECRET": "",
}


class BillingCheckoutAPITest(FirmsAPIFixtureMixin, TestCase):
    """Tests for POST /api/v1/firms/{firm_id}/billing/checkout"""

    URL_TPL = "/api/v1/firms/{firm_id}/billing/checkout"

    def _url(self):
        return self.URL_TPL.format(firm_id=self.firm.id)

    @override_settings(**_STRIPE_SETTINGS)
    @patch("stripe.checkout.Session.create")
    def test_owner_creates_checkout_session(self, mock_create):
        """Owner can create a Checkout session and gets back a URL."""
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/session_abc"
        mock_create.return_value = mock_session

        # Downgrade to free so we can test upgrading.
        self.firm.subscription_tier = "free"
        self.firm.save()

        resp = self._post(self._url(), {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["checkout_url"], "https://checkout.stripe.com/session_abc")
        mock_create.assert_called_once()

    @override_settings(**_STRIPE_SETTINGS)
    def test_worker_cannot_access_billing(self):
        """Only Owners can manage billing."""
        self.client.login(username="worker@api.com", password="pass")
        resp = self._post(self._url(), {})
        self.assertEqual(resp.status_code, 403)

    @override_settings(**_STRIPE_SETTINGS)
    def test_already_pro_returns_400(self):
        """Returns 400 when Firm already has an active Pro subscription."""
        # The FirmsAPIFixtureMixin already sets subscription_tier="pro".
        resp = self._post(self._url(), {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already has an active Pro", resp.json()["detail"])

    def test_stripe_not_configured_returns_400(self):
        """Returns 400 gracefully when Stripe env vars are missing."""
        self.firm.subscription_tier = "free"
        self.firm.save()
        with override_settings(STRIPE_SECRET_KEY="", STRIPE_PRICE_ID=""):
            resp = self._post(self._url(), {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not configured", resp.json()["detail"])

    def test_unauthenticated_returns_error(self):
        self.client.logout()
        resp = self._post(self._url(), {})
        self.assertIn(resp.status_code, [401, 403])

    @override_settings(**_STRIPE_SETTINGS)
    def test_nonexistent_firm_returns_404(self):
        resp = self._post(self.URL_TPL.format(firm_id=uuid.uuid4()), {})
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Stripe webhook tests
# ---------------------------------------------------------------------------

WEBHOOK_URL = "/api/v1/stripe/webhook"


def _post_webhook(client, payload):
    """POST a JSON payload to the webhook endpoint (no signature verification)."""
    return client.post(
        WEBHOOK_URL,
        data=json.dumps(payload),
        content_type="application/json",
    )


class StripeWebhookCheckoutCompletedTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Webhook Firm", subscription_tier="free")

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_checkout_completed_upgrades_firm_to_pro(self):
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_abc",
                    "customer": "cus_123",
                    "subscription": "sub_456",
                    "metadata": {"firm_id": str(self.firm.id)},
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)
        self.firm.refresh_from_db()
        self.assertEqual(self.firm.subscription_tier, "pro")
        self.assertTrue(self.firm.subscription_active)
        self.assertEqual(self.firm.stripe_customer_id, "cus_123")
        self.assertEqual(self.firm.stripe_subscription_id, "sub_456")

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_checkout_completed_missing_firm_id_does_not_crash(self):
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_abc",
                    "customer": "cus_123",
                    "subscription": "sub_456",
                    "metadata": {},
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)


class StripeWebhookSubscriptionUpdatedTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(
            name="Sub Firm",
            subscription_tier="pro",
            subscription_active=True,
            stripe_subscription_id="sub_789",
        )

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_subscription_updated_past_due_deactivates(self):
        event = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_789",
                    "status": "past_due",
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)
        self.firm.refresh_from_db()
        self.assertFalse(self.firm.subscription_active)

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_subscription_updated_active_reactivates(self):
        self.firm.subscription_active = False
        self.firm.save()
        event = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_789",
                    "status": "active",
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)
        self.firm.refresh_from_db()
        self.assertTrue(self.firm.subscription_active)

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_subscription_updated_unknown_id_does_not_crash(self):
        event = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_nonexistent",
                    "status": "active",
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)


class StripeWebhookSubscriptionDeletedTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(
            name="Deleted Sub Firm",
            subscription_tier="pro",
            subscription_active=True,
            stripe_subscription_id="sub_del_123",
        )

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_subscription_deleted_downgrades_to_free(self):
        event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_del_123",
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)
        self.firm.refresh_from_db()
        self.assertEqual(self.firm.subscription_tier, "free")
        self.assertTrue(self.firm.subscription_active)
        self.assertEqual(self.firm.stripe_subscription_id, "")


class StripeWebhookPaymentFailedTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(
            name="Payment Failed Firm",
            subscription_tier="pro",
            subscription_active=True,
            stripe_customer_id="cus_fail_456",
        )

    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="")
    def test_payment_failed_marks_subscription_inactive(self):
        event = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_test_abc",
                    "customer": "cus_fail_456",
                }
            },
        }
        resp = _post_webhook(self.client, event)
        self.assertEqual(resp.status_code, 200)
        self.firm.refresh_from_db()
        self.assertFalse(self.firm.subscription_active)


class StripeWebhookSignatureTest(TestCase):
    @override_settings(STRIPE_SECRET_KEY="sk_test_fake", STRIPE_WEBHOOK_SECRET="whsec_test")
    def test_invalid_signature_returns_400(self):
        """Requests without a valid Stripe-Signature must be rejected."""
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {}},
        }
        resp = self.client.post(
            WEBHOOK_URL,
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=invalidsig",
        )
        self.assertEqual(resp.status_code, 400)

    def test_stripe_not_configured_returns_400(self):
        """Webhook returns 400 when STRIPE_SECRET_KEY is missing."""
        with override_settings(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET=""):
            resp = _post_webhook(self.client, {"type": "ping", "data": {"object": {}}})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Tier limit enforcement through API endpoints
# ---------------------------------------------------------------------------

class TierLimitInviteMemberAPITest(TestCase):
    """invite_member enforces the Free-tier 2-member limit."""

    URL_TPL = "/api/v1/firms/{firm_id}/members"

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@tier.com", password="pass")
        self.worker = User.objects.create_user(email="worker@tier.com", password="pass")
        # Free-tier firm with 2 members — at the limit.
        self.firm = Firm.objects.create(name="Free Tier Firm", subscription_tier="free")
        Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)
        self.client.login(username="owner@tier.com", password="pass")

    def test_invite_third_member_blocked_on_free(self):
        new_user = User.objects.create_user(email="third@tier.com", password="pass")
        resp = self.client.post(
            self.URL_TPL.format(firm_id=self.firm.id),
            data=json.dumps({"email": "third@tier.com", "role": "worker"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 402)
        self.assertIn("2 team members", resp.json()["detail"])


class TierLimitCreateInvitationAPITest(TestCase):
    """create_invitation enforces the Free-tier 2-member limit."""

    URL_TPL = "/api/v1/firms/{firm_id}/invitations/"

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@inv_tier.com", password="pass")
        self.worker = User.objects.create_user(email="worker@inv_tier.com", password="pass")
        self.firm = Firm.objects.create(name="Free Inv Firm", subscription_tier="free")
        Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)
        self.client.login(username="owner@inv_tier.com", password="pass")

    def test_invite_third_member_blocked_on_free(self):
        resp = self.client.post(
            self.URL_TPL.format(firm_id=self.firm.id),
            data=json.dumps({"email": "newperson@example.com", "role": "worker"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 402)
        self.assertIn("2 team members", resp.json()["detail"])

    def test_resend_existing_invitation_not_blocked(self):
        """Re-sending an existing invitation should not trigger the member limit."""
        Invitation.objects.create(
            email="pending@example.com",
            firm=self.firm,
            invited_by=self.owner,
        )
        resp = self.client.post(
            self.URL_TPL.format(firm_id=self.firm.id),
            data=json.dumps({"email": "pending@example.com", "role": "worker"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 202)


# ===========================================================================
# v1.7 — API Tokens
# ===========================================================================

class APITokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="token@example.com", password="pass")
        self.firm = Firm.objects.create(name="Token Firm")
        Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.OWNER)

    def test_create_for_user_returns_plain_text(self):
        from firms.models import APIToken
        token_obj, plain = APIToken.create_for_user(
            firm=self.firm, user=self.user, name="CI Token"
        )
        self.assertIsNotNone(plain)
        self.assertTrue(len(plain) > 8)
        self.assertEqual(token_obj.name, "CI Token")
        self.assertTrue(token_obj.is_active)

    def test_authenticate_valid_token(self):
        from firms.models import APIToken
        token_obj, plain = APIToken.create_for_user(
            firm=self.firm, user=self.user, name="Auth Test"
        )
        found = APIToken.authenticate(plain)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, token_obj.id)

    def test_authenticate_wrong_token(self):
        from firms.models import APIToken
        result = APIToken.authenticate("totallyinvalidtoken")
        self.assertIsNone(result)

    def test_revoked_token_is_inactive(self):
        from firms.models import APIToken
        from django.utils import timezone
        token_obj, plain = APIToken.create_for_user(
            firm=self.firm, user=self.user, name="Rev Test"
        )
        token_obj.revoked_at = timezone.now()
        token_obj.save(update_fields=["revoked_at"])
        self.assertFalse(token_obj.is_active)
        result = APIToken.authenticate(plain)
        self.assertIsNone(result)


class APITokenEndpointTest(TestCase):
    """Integration tests for the /api/v1/firms/{id}/tokens endpoints."""

    def setUp(self):
        self.owner = User.objects.create_user(email="token_owner@example.com", password="pass")
        self.firm = Firm.objects.create(name="Token Endpoint Firm")
        Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_create_token(self):
        resp = self.client.post(
            f"/api/v1/firms/{self.firm.id}/tokens",
            data=json.dumps({"name": "My Token"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("token", data)
        self.assertIn("prefix", data)
        self.assertTrue(data["is_active"])

    def test_list_tokens(self):
        from firms.models import APIToken
        APIToken.create_for_user(firm=self.firm, user=self.owner, name="T1")
        resp = self.client.get(f"/api/v1/firms/{self.firm.id}/tokens")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 1)

    def test_revoke_token(self):
        from firms.models import APIToken
        token_obj, _ = APIToken.create_for_user(
            firm=self.firm, user=self.owner, name="Rev Token"
        )
        resp = self.client.delete(f"/api/v1/firms/{self.firm.id}/tokens/{token_obj.id}")
        self.assertEqual(resp.status_code, 204)
        token_obj.refresh_from_db()
        self.assertIsNotNone(token_obj.revoked_at)


# ===========================================================================
# v1.7 — Webhooks
# ===========================================================================

class WebhookEndpointModelTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Webhook Firm")

    def test_subscribes_to_empty_events_means_all(self):
        from firms.models import WebhookEndpoint
        ep = WebhookEndpoint(firm=self.firm, url="https://example.com", events=[])
        self.assertTrue(ep.subscribes_to("record.created"))
        self.assertTrue(ep.subscribes_to("activity.created"))

    def test_subscribes_to_specific_event(self):
        from firms.models import WebhookEndpoint
        ep = WebhookEndpoint(firm=self.firm, url="https://example.com", events=["record.created"])
        self.assertTrue(ep.subscribes_to("record.created"))
        self.assertFalse(ep.subscribes_to("activity.created"))


class WebhookAPITest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="wh_owner@example.com", password="pass")
        self.firm = Firm.objects.create(name="Webhook API Firm")
        Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.client.force_login(self.owner)
        self.client.defaults["HTTP_X_FIRM_ID"] = str(self.firm.id)

    def test_create_webhook(self):
        resp = self.client.post(
            f"/api/v1/firms/{self.firm.id}/webhooks",
            data=json.dumps({"url": "https://example.com/hook", "events": ["record.created"]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["url"], "https://example.com/hook")
        self.assertEqual(data["events"], ["record.created"])
        self.assertTrue(data["is_active"])

    def test_list_webhooks(self):
        from firms.models import WebhookEndpoint
        WebhookEndpoint.objects.create(firm=self.firm, url="https://example.com/hook")
        resp = self.client.get(f"/api/v1/firms/{self.firm.id}/webhooks")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 1)

    def test_delete_webhook(self):
        from firms.models import WebhookEndpoint
        ep = WebhookEndpoint.objects.create(firm=self.firm, url="https://example.com/hook")
        resp = self.client.delete(f"/api/v1/firms/{self.firm.id}/webhooks/{ep.id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(WebhookEndpoint.objects.filter(id=ep.id).exists())

    def test_update_webhook(self):
        from firms.models import WebhookEndpoint
        ep = WebhookEndpoint.objects.create(firm=self.firm, url="https://example.com/hook")
        resp = self.client.patch(
            f"/api/v1/firms/{self.firm.id}/webhooks/{ep.id}",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_active"])

    def test_worker_cannot_manage_webhooks(self):
        worker = User.objects.create_user(email="wh_worker@example.com", password="pass")
        Membership.objects.create(user=worker, firm=self.firm, role=MembershipRole.WORKER)
        self.client.force_login(worker)
        resp = self.client.get(f"/api/v1/firms/{self.firm.id}/webhooks")
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Permission matrix tests (Phase 1 – firms.permissions)
# ---------------------------------------------------------------------------


class PermissionMatrixTests(TestCase):
    """
    Verify that LEGACY_ROLE_PERMISSIONS correctly maps every combination of
    role × permission to the expected ALLOW / DENY outcome.

    These tests act as a regression guard: if the mapping is accidentally
    changed, at least one assertion here will fail.
    """

    def setUp(self):
        from firms.permissions import Permission, can, has_min_role

        self.Permission = Permission
        self.can = can
        self.has_min_role = has_min_role

        self.user = User.objects.create_user(email="perm_user@test.com", password="pass")
        self.firm = Firm.objects.create(name="Perm Firm")
        self.owner_m = Membership.objects.create(
            user=self.user, firm=self.firm, role=MembershipRole.OWNER
        )
        # Additional users for admin / worker memberships
        self.admin_user = User.objects.create_user(email="perm_admin@test.com", password="pass")
        self.admin_m = Membership.objects.create(
            user=self.admin_user, firm=self.firm, role=MembershipRole.ADMIN
        )
        self.worker_user = User.objects.create_user(email="perm_worker@test.com", password="pass")
        self.worker_m = Membership.objects.create(
            user=self.worker_user, firm=self.firm, role=MembershipRole.WORKER
        )

    # --- Owner: should have ALL permissions ---

    def test_owner_has_record_view(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.RECORD_VIEW))

    def test_owner_has_record_create(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.RECORD_CREATE))

    def test_owner_has_record_edit(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.RECORD_EDIT))

    def test_owner_has_record_delete(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.RECORD_DELETE))

    def test_owner_has_category_manage(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.CATEGORY_MANAGE))

    def test_owner_has_role_manage(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.ROLE_MANAGE))

    def test_owner_has_billing_manage(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.BILLING_MANAGE))

    def test_owner_has_firm_delete(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.FIRM_DELETE))

    def test_owner_has_firm_transfer(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.FIRM_TRANSFER))

    def test_owner_has_integrations_manage(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.INTEGRATIONS_MANAGE))

    def test_owner_has_team_manage(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.TEAM_MANAGE))

    def test_owner_has_streamline_view_all(self):
        self.assertTrue(self.can(self.owner_m, self.Permission.STREAMLINE_VIEW_ALL))

    # --- Admin: has most permissions but NOT billing/firm-ownership ---

    def test_admin_has_record_view(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.RECORD_VIEW))

    def test_admin_has_record_create(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.RECORD_CREATE))

    def test_admin_has_record_edit(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.RECORD_EDIT))

    def test_admin_has_record_delete(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.RECORD_DELETE))

    def test_admin_has_category_manage(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.CATEGORY_MANAGE))

    def test_admin_has_role_manage(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.ROLE_MANAGE))

    def test_admin_has_team_manage(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.TEAM_MANAGE))

    def test_admin_has_integrations_manage(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.INTEGRATIONS_MANAGE))

    def test_admin_has_streamline_view_all(self):
        self.assertTrue(self.can(self.admin_m, self.Permission.STREAMLINE_VIEW_ALL))

    def test_admin_lacks_billing_manage(self):
        self.assertFalse(self.can(self.admin_m, self.Permission.BILLING_MANAGE))

    def test_admin_lacks_firm_delete(self):
        self.assertFalse(self.can(self.admin_m, self.Permission.FIRM_DELETE))

    def test_admin_lacks_firm_transfer(self):
        self.assertFalse(self.can(self.admin_m, self.Permission.FIRM_TRANSFER))

    # --- Worker: basic CRM actions only ---

    def test_worker_has_record_view(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.RECORD_VIEW))

    def test_worker_has_record_create(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.RECORD_CREATE))

    def test_worker_has_record_edit(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.RECORD_EDIT))

    def test_worker_has_record_delete(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.RECORD_DELETE))

    def test_worker_has_activity_create(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.ACTIVITY_CREATE))

    def test_worker_has_proposal_create(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.PROPOSAL_CREATE))

    def test_worker_has_category_view(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.CATEGORY_VIEW))

    def test_worker_has_report_view(self):
        self.assertTrue(self.can(self.worker_m, self.Permission.REPORT_VIEW))

    def test_worker_lacks_category_manage(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.CATEGORY_MANAGE))

    def test_worker_lacks_role_manage(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.ROLE_MANAGE))

    def test_worker_lacks_team_manage(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.TEAM_MANAGE))

    def test_worker_lacks_billing_manage(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.BILLING_MANAGE))

    def test_worker_lacks_firm_delete(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.FIRM_DELETE))

    def test_worker_lacks_firm_transfer(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.FIRM_TRANSFER))

    def test_worker_lacks_integrations_manage(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.INTEGRATIONS_MANAGE))

    def test_worker_lacks_streamline_view_all(self):
        self.assertFalse(self.can(self.worker_m, self.Permission.STREAMLINE_VIEW_ALL))

    # --- has_min_role: backward-compat bridge ---

    def test_owner_passes_owner_min_role(self):
        self.assertTrue(self.has_min_role(self.owner_m, MembershipRole.OWNER))

    def test_owner_passes_admin_min_role(self):
        self.assertTrue(self.has_min_role(self.owner_m, MembershipRole.ADMIN))

    def test_owner_passes_worker_min_role(self):
        self.assertTrue(self.has_min_role(self.owner_m, MembershipRole.WORKER))

    def test_admin_fails_owner_min_role(self):
        self.assertFalse(self.has_min_role(self.admin_m, MembershipRole.OWNER))

    def test_admin_passes_admin_min_role(self):
        self.assertTrue(self.has_min_role(self.admin_m, MembershipRole.ADMIN))

    def test_admin_passes_worker_min_role(self):
        self.assertTrue(self.has_min_role(self.admin_m, MembershipRole.WORKER))

    def test_worker_fails_owner_min_role(self):
        self.assertFalse(self.has_min_role(self.worker_m, MembershipRole.OWNER))

    def test_worker_fails_admin_min_role(self):
        self.assertFalse(self.has_min_role(self.worker_m, MembershipRole.ADMIN))

    def test_worker_passes_worker_min_role(self):
        self.assertTrue(self.has_min_role(self.worker_m, MembershipRole.WORKER))

    def test_unknown_min_role_denied(self):
        self.assertFalse(self.has_min_role(self.worker_m, "superuser"))


# ---------------------------------------------------------------------------
# Phase 2 – Model tests: PermissionRecord, Role, RolePermission, Team, TeamMembership
# ---------------------------------------------------------------------------

from firms.models import PermissionRecord, Role, RolePermission, Team, TeamMembership


class PermissionRecordModelTest(TestCase):
    def test_create_and_str(self):
        p = PermissionRecord.objects.create(
            code="custom.action",
            group="Custom",
            description="A custom action",
        )
        self.assertEqual(str(p), "custom.action")

    def test_code_is_primary_key(self):
        p = PermissionRecord.objects.create(code="pk.test", group="Test", description="")
        self.assertEqual(p.pk, "pk.test")

    def test_ordering_by_group_then_code(self):
        # Create some records in a specific non-alphabetical order.
        PermissionRecord.objects.create(code="z.action", group="A", description="")
        PermissionRecord.objects.create(code="a.action", group="B", description="")
        PermissionRecord.objects.create(code="m.action", group="A", description="")
        # Within group "A", codes should appear alphabetically.
        group_a = list(
            PermissionRecord.objects.filter(group="A").values_list("code", flat=True)
        )
        self.assertEqual(group_a, sorted(group_a))


class RoleModelTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Role Test Firm")

    def test_create_role(self):
        role = Role.objects.create(
            firm=self.firm,
            code="sales-lead",
            name="Sales Lead",
            is_system=False,
            description="Leads the sales team",
        )
        self.assertIsNotNone(role.id)
        self.assertIn("Sales Lead", str(role))
        self.assertIn("Role Test Firm", str(role))

    def test_unique_together_firm_code(self):
        from django.db import IntegrityError
        Role.objects.create(firm=self.firm, code="dup-role", name="Dup")
        with self.assertRaises(IntegrityError):
            Role.objects.create(firm=self.firm, code="dup-role", name="Dup 2")

    def test_same_code_different_firms(self):
        firm2 = Firm.objects.create(name="Other Firm")
        r1 = Role.objects.create(firm=self.firm, code="analyst", name="Analyst")
        r2 = Role.objects.create(firm=firm2, code="analyst", name="Analyst")
        self.assertNotEqual(r1.id, r2.id)

    def test_assign_permissions_via_role_permission(self):
        role = Role.objects.create(firm=self.firm, code="tester", name="Tester")
        perm = PermissionRecord.objects.create(code="test.perm", group="Test", description="")
        RolePermission.objects.create(role=role, permission=perm)
        self.assertIn(perm, role.permissions.all())


class TeamModelTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Team Test Firm")

    def test_create_team_auto_slug(self):
        team = Team(firm=self.firm, name="Sales West")
        team.save()
        self.assertEqual(team.slug, "sales-west")
        self.assertIn("Sales West", str(team))

    def test_slug_uniqueness_within_firm(self):
        Team.objects.create(firm=self.firm, name="Alpha")
        t2 = Team(firm=self.firm, name="Alpha")
        t2.save()
        self.assertNotEqual(t2.slug, "alpha")
        self.assertTrue(t2.slug.startswith("alpha-"))

    def test_same_slug_different_firms_allowed(self):
        firm2 = Firm.objects.create(name="Other Firm")
        t1 = Team.objects.create(firm=self.firm, name="Alpha")
        t2 = Team.objects.create(firm=firm2, name="Alpha")
        self.assertEqual(t1.slug, t2.slug)

    def test_unique_together_firm_slug(self):
        from django.db import IntegrityError
        Team.objects.create(firm=self.firm, name="Bravo", slug="bravo")
        with self.assertRaises(IntegrityError):
            Team.objects.create(firm=self.firm, name="Bravo 2", slug="bravo")


class TeamMembershipModelTest(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="TM Firm")
        self.owner = User.objects.create_user(email="tm-owner@example.com", password="pass")
        self.member = User.objects.create_user(email="tm-member@example.com", password="pass")
        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.member_m = Membership.objects.create(user=self.member, firm=self.firm, role=MembershipRole.WORKER)
        self.team = Team.objects.create(firm=self.firm, name="Engineering")

    def test_add_membership_to_team(self):
        tm = TeamMembership.objects.create(team=self.team, membership=self.member_m)
        self.assertIsNotNone(tm.joined_at)
        self.assertIn(str(self.team), str(tm))

    def test_unique_team_membership(self):
        from django.db import IntegrityError
        TeamMembership.objects.create(team=self.team, membership=self.member_m)
        with self.assertRaises(IntegrityError):
            TeamMembership.objects.create(team=self.team, membership=self.member_m)


class MembershipPhase2FieldsTest(TestCase):
    """Verify the new Phase-2 fields on Membership."""

    def setUp(self):
        self.firm = Firm.objects.create(name="P2 Firm")
        self.user = User.objects.create_user(email="p2-user@example.com", password="pass")
        self.m = Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.WORKER)

    def test_default_scope_is_own(self):
        self.assertEqual(self.m.default_scope, "own")

    def test_team_fk_nullable(self):
        self.assertIsNone(self.m.team)

    def test_assign_role_to_membership(self):
        role = Role.objects.create(firm=self.firm, code="tester-role", name="Tester")
        self.m.roles.add(role)
        self.assertIn(role, self.m.roles.all())

    def test_assign_team_to_membership(self):
        team = Team.objects.create(firm=self.firm, name="Dev")
        self.m.team = team
        self.m.save()
        self.m.refresh_from_db()
        self.assertEqual(self.m.team, team)

    def test_team_deleted_sets_null(self):
        team = Team.objects.create(firm=self.firm, name="Temp Team")
        self.m.team = team
        self.m.save()
        team.delete()
        self.m.refresh_from_db()
        self.assertIsNone(self.m.team)


# ---------------------------------------------------------------------------
# Phase 2 – Data migration tests (seed_system_roles)
# ---------------------------------------------------------------------------


class SeedSystemRolesDataMigrationTest(TestCase):
    """
    Verify that the 0004_seed_system_roles data migration produces the
    expected system roles and permission assignments.

    The migration runs automatically when the test database is created.
    These tests verify the resulting state using the real model classes.
    """

    def setUp(self):
        self.firm = Firm.objects.create(name="Seed Test Firm")
        # Trigger system role creation for this new firm.
        from firms.migrations._seed_helpers import (
            create_system_roles_for_firm,
            seed_permission_catalogue,
        )
        seed_permission_catalogue()
        create_system_roles_for_firm(self.firm)

        self.owner_user = User.objects.create_user(email="seed-owner@example.com", password="pass")
        self.worker_user = User.objects.create_user(email="seed-worker@example.com", password="pass")
        self.owner_m = Membership.objects.create(
            user=self.owner_user, firm=self.firm, role=MembershipRole.OWNER
        )
        self.worker_m = Membership.objects.create(
            user=self.worker_user, firm=self.firm, role=MembershipRole.WORKER
        )

    def test_system_roles_created_for_firm(self):
        """Each Firm should have four system roles after migration."""
        codes = set(Role.objects.filter(firm=self.firm, is_system=True).values_list("code", flat=True))
        self.assertSetEqual(codes, {"owner", "admin", "member", "guest"})

    def test_permission_catalogue_seeded(self):
        """All 16 permission codes from the Permission enum must be in the catalogue."""
        from firms.permissions import Permission
        db_codes = set(PermissionRecord.objects.values_list("code", flat=True))
        for perm in Permission:
            self.assertIn(perm.value, db_codes, f"{perm.value} missing from catalogue")

    def test_owner_role_has_all_permissions(self):
        owner_role = Role.objects.get(firm=self.firm, code="owner")
        from firms.permissions import Permission
        role_codes = set(owner_role.permissions.values_list("code", flat=True))
        for perm in Permission:
            self.assertIn(perm.value, role_codes, f"Owner missing {perm.value}")

    def test_guest_role_is_read_only(self):
        guest_role = Role.objects.get(firm=self.firm, code="guest")
        role_codes = set(guest_role.permissions.values_list("code", flat=True))
        write_perms = {
            "record.create", "record.edit", "record.delete",
            "category.manage", "team.manage", "role.manage",
            "billing.manage", "firm.delete", "firm.transfer",
            "integrations.manage",
        }
        self.assertTrue(
            write_perms.isdisjoint(role_codes),
            f"Guest has unexpected perms: {write_perms & role_codes}",
        )
        self.assertIn("record.view", role_codes)

    def test_assign_owner_membership_to_system_role(self):
        """Owner Membership can be linked to the 'owner' system role."""
        from firms.migrations._seed_helpers import link_membership_to_system_role
        link_membership_to_system_role(self.owner_m)
        owner_role = Role.objects.get(firm=self.firm, code="owner")
        self.assertIn(owner_role, self.owner_m.roles.all())

    def test_assign_worker_membership_to_member_role(self):
        """Worker Membership can be linked to the 'member' system role."""
        from firms.migrations._seed_helpers import link_membership_to_system_role
        link_membership_to_system_role(self.worker_m)
        member_role = Role.objects.get(firm=self.firm, code="member")
        self.assertIn(member_role, self.worker_m.roles.all())

    def test_multiple_firms_get_independent_roles(self):
        """Roles from different Firms must be separate objects."""
        from firms.migrations._seed_helpers import create_system_roles_for_firm
        firm2 = Firm.objects.create(name="Second Firm")
        create_system_roles_for_firm(firm2)
        owner_role_1 = Role.objects.get(firm=self.firm, code="owner")
        owner_role_2 = Role.objects.get(firm=firm2, code="owner")
        self.assertNotEqual(owner_role_1.id, owner_role_2.id)

    def test_seed_is_idempotent(self):
        """Running the seed twice must not create duplicate roles."""
        from firms.migrations._seed_helpers import create_system_roles_for_firm
        create_system_roles_for_firm(self.firm)
        count = Role.objects.filter(firm=self.firm, is_system=True).count()
        self.assertEqual(count, 4)


# ===========================================================================
# Phase 3 – PermissionAuditLog, CategoryGrant, RecordGrant
# ===========================================================================

class PermissionAuditLogModelTest(TestCase):
    """Unit tests for the PermissionAuditLog model."""

    def setUp(self):
        self.user = User.objects.create_user(email="audit@example.com", password="pass")
        self.firm = Firm.objects.create(name="Audit Test Firm")

    def test_create_audit_log_entry(self):
        """PermissionAuditLog can be created with required fields."""
        from firms.models import PermissionAuditLog
        entry = PermissionAuditLog.objects.create(
            firm=self.firm,
            actor=self.user,
            action="role.created",
            target_type="role",
            target_id="some-uuid",
            payload={"code": "manager", "name": "Manager"},
        )
        self.assertIsNotNone(entry.pk)
        self.assertEqual(entry.action, "role.created")

    def test_audit_log_ordering_descending(self):
        """PermissionAuditLog is ordered by -created_at."""
        from firms.models import PermissionAuditLog
        e1 = PermissionAuditLog.objects.create(
            firm=self.firm, action="role.created", target_type="role", target_id="1"
        )
        e2 = PermissionAuditLog.objects.create(
            firm=self.firm, action="role.deleted", target_type="role", target_id="2"
        )
        qs = list(PermissionAuditLog.objects.filter(firm=self.firm))
        # Most recent first
        self.assertEqual(qs[0].pk, e2.pk)
        self.assertEqual(qs[1].pk, e1.pk)

    def test_audit_log_actor_nullable(self):
        """PermissionAuditLog can be created without an actor (system action)."""
        from firms.models import PermissionAuditLog
        entry = PermissionAuditLog.objects.create(
            firm=self.firm,
            actor=None,
            action="membership.created",
            target_type="membership",
            target_id="abc",
        )
        self.assertIsNone(entry.actor)

    def test_audit_log_str(self):
        """PermissionAuditLog __str__ includes action and target."""
        from firms.models import PermissionAuditLog
        entry = PermissionAuditLog.objects.create(
            firm=self.firm,
            action="role.updated",
            target_type="role",
            target_id="xyz",
        )
        s = str(entry)
        self.assertIn("role.updated", s)
        self.assertIn("xyz", s)


class RoleAuditSignalTest(TestCase):
    """Post-save / post-delete signals on Role create PermissionAuditLog entries."""

    def setUp(self):
        self.firm = Firm.objects.create(name="Signal Test Firm")

    def test_role_created_signal(self):
        """Creating a Role produces a 'role.created' audit entry."""
        from firms.models import PermissionAuditLog, Role
        initial_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="role.created"
        ).count()
        Role.objects.create(firm=self.firm, code="test-role", name="Test Role")
        new_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="role.created"
        ).count()
        self.assertEqual(new_count, initial_count + 1)

    def test_role_deleted_signal(self):
        """Deleting a Role produces a 'role.deleted' audit entry."""
        from firms.models import PermissionAuditLog, Role
        role = Role.objects.create(firm=self.firm, code="delete-me", name="Delete Me")
        initial_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="role.deleted"
        ).count()
        role.delete()
        new_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="role.deleted"
        ).count()
        self.assertEqual(new_count, initial_count + 1)


class MembershipAuditSignalTest(TestCase):
    """Post-save / post-delete signals on Membership create PermissionAuditLog entries."""

    def setUp(self):
        self.firm = Firm.objects.create(name="Membership Signal Firm")
        self.user = User.objects.create_user(email="memb@example.com", password="pass")

    def test_membership_created_signal(self):
        """Creating a Membership produces a 'membership.created' audit entry."""
        from firms.models import PermissionAuditLog
        initial_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="membership.created"
        ).count()
        Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.WORKER)
        new_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="membership.created"
        ).count()
        self.assertEqual(new_count, initial_count + 1)

    def test_membership_deleted_signal(self):
        """Deleting a Membership produces a 'membership.deleted' audit entry."""
        from firms.models import PermissionAuditLog
        m = Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.WORKER)
        initial_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="membership.deleted"
        ).count()
        m.delete()
        new_count = PermissionAuditLog.objects.filter(
            firm=self.firm, action="membership.deleted"
        ).count()
        self.assertEqual(new_count, initial_count + 1)


# ===========================================================================
# Phase 4 – require_permission tests
# ===========================================================================

class RequirePermissionTest(TestCase):
    """Tests for require_permission (always uses V2 DB-backed resolution)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.firm = Firm.objects.create(name="Phase4 Firm")
        self.owner = User.objects.create_user(email="p4owner@example.com", password="pass")
        self.admin = User.objects.create_user(email="p4admin@example.com", password="pass")
        self.worker = User.objects.create_user(email="p4worker@example.com", password="pass")
        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.admin_m = Membership.objects.create(user=self.admin, firm=self.firm, role=MembershipRole.ADMIN)
        self.worker_m = Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)

    def _make_request(self, user, membership):
        req = self.factory.get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_owner_has_all_permissions(self):
        req = self._make_request(self.owner, self.owner_m)
        # Owner should pass every permission check
        for perm in [
            Permission.RECORD_VIEW, Permission.RECORD_CREATE, Permission.RECORD_EDIT,
            Permission.RECORD_DELETE, Permission.BILLING_MANAGE, Permission.FIRM_DELETE,
        ]:
            result = require_permission(req, perm)
            self.assertEqual(result, self.owner_m, f"Owner should have {perm}")

    def test_worker_has_record_permissions(self):
        req = self._make_request(self.worker, self.worker_m)
        for perm in [Permission.RECORD_VIEW, Permission.RECORD_CREATE, Permission.RECORD_EDIT]:
            result = require_permission(req, perm)
            self.assertEqual(result, self.worker_m)

    def test_worker_denied_billing(self):
        req = self._make_request(self.worker, self.worker_m)
        with self.assertRaises(PermissionDenied):
            require_permission(req, Permission.BILLING_MANAGE)

    def test_worker_denied_role_manage(self):
        req = self._make_request(self.worker, self.worker_m)
        with self.assertRaises(PermissionDenied):
            require_permission(req, Permission.ROLE_MANAGE)

    def test_admin_has_role_manage(self):
        req = self._make_request(self.admin, self.admin_m)
        result = require_permission(req, Permission.ROLE_MANAGE)
        self.assertEqual(result, self.admin_m)

    def test_admin_denied_billing(self):
        req = self._make_request(self.admin, self.admin_m)
        with self.assertRaises(PermissionDenied):
            require_permission(req, Permission.BILLING_MANAGE)

    def test_unauthenticated_raises(self):
        req = self.factory.get("/")
        req.user = MagicMock(is_authenticated=False)
        req.firm = self.firm
        from firms.auth import AuthenticationRequired
        with self.assertRaises(AuthenticationRequired):
            require_permission(req, Permission.RECORD_VIEW)

    def test_no_membership_raises(self):
        req = self.factory.get("/")
        req.user = self.worker
        req.firm = self.firm
        req.membership = None
        with self.assertRaises(PermissionDenied):
            require_permission(req, Permission.RECORD_VIEW)


class RequirePermissionV2FlagTest(TestCase):
    """Tests for require_permission using DB-backed role resolution."""

    def setUp(self):
        self.factory = RequestFactory()
        self.firm = Firm.objects.create(name="Phase4V2 Firm")
        self.owner = User.objects.create_user(email="v2owner@example.com", password="pass")
        self.worker = User.objects.create_user(email="v2worker@example.com", password="pass")
        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.worker_m = Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)

    def _make_request(self, user, membership):
        req = self.factory.get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_owner_passes_all_v2(self):
        """Owner always passes (shortcut path)."""
        req = self._make_request(self.owner, self.owner_m)
        result = require_permission(req, Permission.BILLING_MANAGE)
        self.assertEqual(result, self.owner_m)

    def test_worker_with_db_role_record_view(self):
        """Worker with DB 'member' system role can view records."""
        from firms.models import Role
        # Seed system roles for this firm (normally done by data migration)
        from firms.migrations._seed_helpers import create_system_roles_for_firm as seed_system_roles_for_firm
        seed_system_roles_for_firm(self.firm)
        member_role = Role.objects.get(firm=self.firm, code="member")
        self.worker_m.roles.add(member_role)

        req = self._make_request(self.worker, self.worker_m)
        result = require_permission(req, Permission.RECORD_VIEW)
        self.assertEqual(result, self.worker_m)

    def test_worker_without_db_role_uses_legacy_fallback(self):
        """When no DB roles assigned, legacy map is used as fallback."""
        req = self._make_request(self.worker, self.worker_m)
        # Worker legacy map includes RECORD_VIEW
        result = require_permission(req, Permission.RECORD_VIEW)
        self.assertEqual(result, self.worker_m)

    def test_worker_denied_billing_v2(self):
        """Worker cannot access billing (no roles assigned, falls back to legacy)."""
        req = self._make_request(self.worker, self.worker_m)
        with self.assertRaises(PermissionDenied):
            require_permission(req, Permission.BILLING_MANAGE)


# ===========================================================================
# Phase 6 – Roles API & Teams API tests
# ===========================================================================


class RolesAPITest(TestCase):
    """Tests for firms/roles_api.py endpoints."""

    def setUp(self):
        from firms.models import PermissionRecord, Role
        self.factory = RequestFactory()
        self.firm = Firm.objects.create(name="RolesAPIFirm")
        self.owner = User.objects.create_user(email="rolesowner@example.com", password="pass")
        self.admin = User.objects.create_user(email="rolesadmin@example.com", password="pass")
        self.worker = User.objects.create_user(email="rolesworker@example.com", password="pass")
        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.admin_m = Membership.objects.create(user=self.admin, firm=self.firm, role=MembershipRole.ADMIN)
        self.worker_m = Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)

    def _make_request(self, user, membership):
        req = self.factory.get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_list_roles_returns_system_roles(self):
        """list_roles returns at least the seeded system roles for the firm."""
        from firms.roles_api import list_roles
        req = self._make_request(self.owner, self.owner_m)
        status, result = list_roles(req, firm_id=str(self.firm.id))
        self.assertEqual(status, 200)
        codes = [r["code"] for r in result]
        self.assertIn("owner", codes)
        self.assertIn("member", codes)

    def test_permission_catalogue_returned(self):
        """list_permission_catalogue returns PermissionRecord entries."""
        from firms.roles_api import list_permission_catalogue
        req = self._make_request(self.worker, self.worker_m)
        status, result = list_permission_catalogue(req, firm_id=str(self.firm.id))
        self.assertEqual(status, 200)
        self.assertGreater(len(result), 0)
        codes = [p["code"] for p in result]
        self.assertIn("record.view", codes)

    def test_create_custom_role(self):
        """Admin can create a custom role with non-elevated permissions."""
        from firms.roles_api import create_role, RoleCreateIn
        # Give admin the role.manage permission via system role
        from firms.models import Role as RoleModel
        admin_sys_role = RoleModel.objects.get(firm=self.firm, code="admin")
        self.admin_m.roles.add(admin_sys_role)

        req = self._make_request(self.admin, self.admin_m)
        payload = RoleCreateIn(
            code="sales-lead",
            name="Sales Lead",
            permissions=["record.view", "record.create"],
        )
        status, result = create_role(req, firm_id=str(self.firm.id), payload=payload)
        self.assertEqual(status, 201)
        self.assertEqual(result["code"], "sales-lead")
        self.assertIn("record.view", result["permissions"])

    def test_worker_cannot_create_role(self):
        """Worker without role.manage permission is denied."""
        from firms.roles_api import create_role, RoleCreateIn
        req = self._make_request(self.worker, self.worker_m)
        payload = RoleCreateIn(code="x", name="X")
        status, result = create_role(req, firm_id=str(self.firm.id), payload=payload)
        self.assertEqual(status, 403)

    def test_cannot_delete_system_role(self):
        """Attempting to delete a system role returns 403."""
        from firms.roles_api import delete_role
        from firms.models import Role as RoleModel
        # Give owner the role.manage permission via its system role
        owner_sys_role = RoleModel.objects.get(firm=self.firm, code="owner")
        self.owner_m.roles.add(owner_sys_role)
        system_role = RoleModel.objects.get(firm=self.firm, code="member")
        req = self._make_request(self.owner, self.owner_m)
        status, result = delete_role(req, firm_id=str(self.firm.id), role_id=str(system_role.id))
        self.assertEqual(status, 403)


class TeamsAPITest(TestCase):
    """Tests for firms/teams_api.py endpoints."""

    def setUp(self):
        self.factory = RequestFactory()
        self.firm = Firm.objects.create(name="TeamsAPIFirm")
        self.owner = User.objects.create_user(email="teamsowner@example.com", password="pass")
        self.worker = User.objects.create_user(email="teamsworker@example.com", password="pass")
        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.worker_m = Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)

    def _make_request(self, user, membership):
        req = self.factory.get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_list_teams_empty(self):
        from firms.teams_api import list_teams
        req = self._make_request(self.owner, self.owner_m)
        status, result = list_teams(req, firm_id=str(self.firm.id))
        self.assertEqual(status, 200)
        self.assertEqual(result, [])

    def test_create_team(self):
        from firms.teams_api import create_team, TeamCreateIn
        req = self._make_request(self.owner, self.owner_m)
        payload = TeamCreateIn(name="Sales CZ", color="#ff0000")
        status, result = create_team(req, firm_id=str(self.firm.id), payload=payload)
        self.assertEqual(status, 201)
        self.assertEqual(result["name"], "Sales CZ")
        self.assertEqual(result["color"], "#ff0000")
        self.assertEqual(result["member_count"], 0)

    def test_worker_cannot_create_team(self):
        from firms.teams_api import create_team, TeamCreateIn
        req = self._make_request(self.worker, self.worker_m)
        payload = TeamCreateIn(name="Unauthorized")
        status, _ = create_team(req, firm_id=str(self.firm.id), payload=payload)
        self.assertEqual(status, 403)

    def test_add_and_remove_team_member(self):
        from firms.teams_api import create_team, add_team_member, remove_team_member, TeamCreateIn
        # Create a team first
        req = self._make_request(self.owner, self.owner_m)
        _, team = create_team(req, firm_id=str(self.firm.id), payload=TeamCreateIn(name="Dev Team"))

        # Add worker to team
        status, result = add_team_member(
            req,
            firm_id=str(self.firm.id),
            team_id=team["id"],
            membership_id=str(self.worker_m.id),
        )
        self.assertEqual(status, 201)
        self.assertEqual(result["member_count"], 1)

        # Remove worker from team
        status, result = remove_team_member(
            req,
            firm_id=str(self.firm.id),
            team_id=team["id"],
            membership_id=str(self.worker_m.id),
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["member_count"], 0)

    def test_delete_team(self):
        from firms.teams_api import create_team, delete_team, TeamCreateIn
        from firms.models import Team
        req = self._make_request(self.owner, self.owner_m)
        _, team = create_team(req, firm_id=str(self.firm.id), payload=TeamCreateIn(name="Temp"))
        status, _ = delete_team(req, firm_id=str(self.firm.id), team_id=team["id"])
        self.assertEqual(status, 204)
        self.assertFalse(Team.objects.filter(id=team["id"]).exists())


class AuditLogAPITest(TestCase):
    """Tests for the GET /firms/{id}/audit-log endpoint."""

    def setUp(self):
        self.factory = RequestFactory()
        self.firm = Firm.objects.create(name="AuditFirm")
        self.owner = User.objects.create_user(email="auditowner@example.com", password="pass")
        self.worker = User.objects.create_user(email="auditworker@example.com", password="pass")
        self.owner_m = Membership.objects.create(user=self.owner, firm=self.firm, role=MembershipRole.OWNER)
        self.worker_m = Membership.objects.create(user=self.worker, firm=self.firm, role=MembershipRole.WORKER)

    def _make_request(self, user, membership):
        req = self.factory.get("/")
        req.user = user
        req.firm = self.firm
        req.membership = membership
        return req

    def test_owner_can_read_audit_log(self):
        from firms.api import list_audit_log
        req = self._make_request(self.owner, self.owner_m)
        status, result = list_audit_log(req, firm_id=str(self.firm.id))
        self.assertEqual(status, 200)
        self.assertIsInstance(result, list)

    def test_worker_denied_audit_log(self):
        from firms.api import list_audit_log
        req = self._make_request(self.worker, self.worker_m)
        status, _ = list_audit_log(req, firm_id=str(self.firm.id))
        self.assertEqual(status, 403)

    def test_audit_log_contains_membership_events(self):
        """Audit log should contain the membership.created event from setUp."""
        from firms.api import list_audit_log
        from firms.models import PermissionAuditLog
        # Manually create an audit entry for this firm
        PermissionAuditLog.objects.create(
            firm=self.firm,
            actor=self.owner,
            action="role.created",
            target_type="role",
            target_id="test-id",
            payload={"code": "test"},
        )
        req = self._make_request(self.owner, self.owner_m)
        status, result = list_audit_log(req, firm_id=str(self.firm.id))
        self.assertEqual(status, 200)
        actions = [e["action"] for e in result]
        self.assertIn("role.created", actions)


# ===========================================================================
# v2.1 – Sync legacy role → M2M roles
# ===========================================================================


class LegacyRoleSyncTest(TestCase):
    """Tests for _sync_legacy_role_to_m2m() and the post_save signal wiring."""

    def setUp(self):
        self.firm = Firm.objects.create(name="Sync Test Firm")
        self.user = User.objects.create_user(email="synctestuser@example.com", password="pass")

    def test_new_membership_syncs_system_role(self):
        """Creating a Membership with role='worker' should auto-assign the 'member' system Role.

        WORKER is a deprecated alias for MEMBER; the sync maps both to the 'member' system role.
        """
        m = Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.WORKER)
        role_codes = list(m.roles.values_list("code", flat=True))
        # WORKER maps to the 'member' system role via LEGACY_TO_SYSTEM_ROLE
        self.assertIn(
            "member",
            role_codes,
            f"Expected 'member' system role in M2M (WORKER→MEMBER alias), got: {role_codes}",
        )

    def test_sync_helper_updates_m2m_on_role_change(self):
        """Calling _sync_legacy_role_to_m2m() after changing legacy role updates M2M."""
        m = Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.WORKER)
        # Change the legacy role and call sync manually
        m.role = MembershipRole.ADMIN
        m.save(update_fields=["role"])
        # Signal should have synced M2M; admin system role should now be present
        m.refresh_from_db()
        role_codes = list(m.roles.values_list("code", flat=True))
        self.assertIn("admin", role_codes, f"Expected 'admin' in M2M roles, got: {role_codes}")

    def test_primary_role_prefers_m2m_over_legacy(self):
        """primary_role returns M2M-derived role even if legacy field differs."""
        m = Membership.objects.create(user=self.user, firm=self.firm, role=MembershipRole.WORKER)
        # Manually set an 'admin' M2M role without touching legacy field
        from firms.models import Role
        admin_role = Role.objects.filter(firm=self.firm, code="admin", is_system=True).first()
        if admin_role:
            m.roles.set([admin_role])
            # primary_role should see 'admin' from M2M despite legacy field being 'worker'
            self.assertEqual(m.primary_role, "admin")

    def test_membership_out_uses_primary_role(self):
        """_membership_out serialiser returns primary_role not legacy role field."""
        from firms.api import _membership_out
        m = Membership.objects.create(
            user=self.user, firm=self.firm, role=MembershipRole.WORKER
        )
        result = _membership_out(m)
        # primary_role should match (via M2M or fallback to legacy)
        self.assertEqual(result["role"], m.primary_role)
