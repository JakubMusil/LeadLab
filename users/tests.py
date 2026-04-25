from django.test import TestCase

from users.models import User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(email="alice@example.com", password="pass1234")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        su = User.objects.create_superuser(email="admin@example.com", password="admin1234")
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)

    def test_email_is_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_full_name_property(self):
        user = User.objects.create_user(
            email="bob@example.com", password="pass", first_name="Bob", last_name="Builder"
        )
        self.assertEqual(user.full_name, "Bob Builder")

    def test_full_name_falls_back_to_email(self):
        user = User.objects.create_user(email="noname@example.com", password="pass")
        self.assertEqual(user.full_name, "noname@example.com")

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pass")

    def test_email_is_normalized(self):
        user = User.objects.create_user(email="Test@EXAMPLE.COM", password="pass")
        self.assertEqual(user.email, "Test@example.com")

    def test_default_timezone(self):
        user = User.objects.create_user(email="tz@example.com", password="pass")
        self.assertEqual(user.timezone, "UTC")


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

import json


class UserAPITest(TestCase):
    REGISTER_URL = "/api/v1/users/register"
    LOGIN_URL = "/api/v1/users/login"
    LOGOUT_URL = "/api/v1/users/logout"
    ME_URL = "/api/v1/users/me"

    def _post(self, url, data):
        return self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

    def test_register_creates_user(self):
        resp = self._post(self.REGISTER_URL, {"email": "new@example.com", "password": "pass1234"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["email"], "new@example.com")
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_register_duplicate_email_returns_400(self):
        User.objects.create_user(email="dup@example.com", password="pass")
        resp = self._post(self.REGISTER_URL, {"email": "dup@example.com", "password": "pass"})
        self.assertEqual(resp.status_code, 400)

    def test_login_success(self):
        User.objects.create_user(email="login@example.com", password="correct")
        resp = self._post(self.LOGIN_URL, {"email": "login@example.com", "password": "correct"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email"], "login@example.com")

    def test_login_wrong_password_returns_401(self):
        User.objects.create_user(email="u@example.com", password="correct")
        resp = self._post(self.LOGIN_URL, {"email": "u@example.com", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)

    def test_me_requires_authentication(self):
        resp = self.client.get(self.ME_URL)
        self.assertIn(resp.status_code, [401, 403])

    def test_me_returns_current_user(self):
        User.objects.create_user(email="me@example.com", password="pass")
        self.client.login(username="me@example.com", password="pass")
        resp = self.client.get(self.ME_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email"], "me@example.com")

    def test_logout_ends_session(self):
        User.objects.create_user(email="bye@example.com", password="pass")
        self.client.login(username="bye@example.com", password="pass")
        resp = self.client.post(self.LOGOUT_URL, content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        # After logout, /me should be inaccessible
        resp2 = self.client.get(self.ME_URL)
        self.assertIn(resp2.status_code, [401, 403])

    def test_register_stores_first_last_name_and_timezone(self):
        resp = self._post(self.REGISTER_URL, {
            "email": "full@example.com",
            "password": "pass",
            "first_name": "Alice",
            "last_name": "Smith",
            "timezone": "Europe/Prague",
        })
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email="full@example.com")
        self.assertEqual(user.first_name, "Alice")
        self.assertEqual(user.last_name, "Smith")
        self.assertEqual(user.timezone, "Europe/Prague")

