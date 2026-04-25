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
)
from firms.middleware import TenantMiddleware
from firms.models import Firm, Membership
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
        from crm.models import Lead
        for i in range(50):
            Lead.objects.create(firm=self.firm, title=f"Lead {i}")
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
        from crm.models import Lead
        for i in range(100):
            Lead.objects.create(firm=self.firm, title=f"Lead {i}")
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
