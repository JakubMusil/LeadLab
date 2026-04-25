from django.test import TestCase, RequestFactory

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
