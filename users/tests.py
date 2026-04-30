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


# ---------------------------------------------------------------------------
# Profile update API tests
# ---------------------------------------------------------------------------

class ProfileUpdateAPITest(TestCase):
    ME_URL = "/api/v1/users/me"

    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            password="pass",
            first_name="Old",
            last_name="Name",
            timezone="UTC",
        )
        self.client.login(username="profile@example.com", password="pass")

    def _patch(self, data):
        import json
        return self.client.patch(
            self.ME_URL, data=json.dumps(data), content_type="application/json"
        )

    def test_update_first_name(self):
        resp = self._patch({"first_name": "New"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["first_name"], "New")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")

    def test_update_last_name(self):
        resp = self._patch({"last_name": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["last_name"], "Updated")

    def test_update_timezone(self):
        resp = self._patch({"timezone": "Europe/Prague"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["timezone"], "Europe/Prague")

    def test_partial_update_preserves_other_fields(self):
        resp = self._patch({"first_name": "Changed"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Other fields should not change
        self.assertEqual(data["last_name"], "Name")
        self.assertEqual(data["timezone"], "UTC")

    def test_empty_patch_is_ok(self):
        resp = self._patch({})
        self.assertEqual(resp.status_code, 200)

    def test_update_profile_requires_authentication(self):
        self.client.logout()
        resp = self._patch({"first_name": "Anon"})
        self.assertIn(resp.status_code, [401, 403])


# ---------------------------------------------------------------------------
# Password reset API tests
# ---------------------------------------------------------------------------

class PasswordResetAPITest(TestCase):
    REQUEST_URL = "/api/v1/users/password-reset/request"
    CONFIRM_URL = "/api/v1/users/password-reset/confirm"

    def setUp(self):
        self.user = User.objects.create_user(
            email="resetme@example.com", password="oldpassword123"
        )

    def _post(self, url, data):
        import json
        return self.client.post(url, data=json.dumps(data), content_type="application/json")

    def test_request_for_existing_email_returns_200(self):
        resp = self._post(self.REQUEST_URL, {"email": "resetme@example.com"})
        self.assertEqual(resp.status_code, 200)

    def test_request_for_nonexistent_email_still_returns_200(self):
        resp = self._post(self.REQUEST_URL, {"email": "nobody@example.com"})
        self.assertEqual(resp.status_code, 200)

    def test_confirm_with_valid_token_resets_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        resp = self._post(self.CONFIRM_URL, {
            "uid": uid,
            "token": token,
            "new_password": "brand-new-password-456",
        })
        self.assertEqual(resp.status_code, 200)
        # Old password should no longer work
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("oldpassword123"))
        self.assertTrue(self.user.check_password("brand-new-password-456"))

    def test_confirm_with_invalid_token_returns_400(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        resp = self._post(self.CONFIRM_URL, {
            "uid": uid,
            "token": "invalid-token",
            "new_password": "newpassword456",
        })
        self.assertEqual(resp.status_code, 400)

    def test_confirm_with_invalid_uid_returns_400(self):
        resp = self._post(self.CONFIRM_URL, {
            "uid": "not-a-valid-uid",
            "token": "sometoken",
            "new_password": "newpassword456",
        })
        self.assertEqual(resp.status_code, 400)



# ---------------------------------------------------------------------------
# Streamline preferences tests
# ---------------------------------------------------------------------------

from users.models import UserStreamlinePreference


class StreamlinePreferenceAPITest(TestCase):
    URL = "/api/v1/users/me/streamline-preferences"

    def setUp(self):
        self.user = User.objects.create_user(email="pref@example.com", password="pass")
        self.client.login(username="pref@example.com", password="pass")

    def _put(self, data):
        return self.client.put(
            self.URL, data=json.dumps(data), content_type="application/json"
        )

    def test_get_default_returns_null(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"visible_activity_types": None})

    def test_get_creates_row_lazily(self):
        self.assertFalse(UserStreamlinePreference.objects.filter(user=self.user).exists())
        self.client.get(self.URL)
        self.assertTrue(UserStreamlinePreference.objects.filter(user=self.user).exists())

    def test_put_persists_explicit_visible_set(self):
        resp = self._put({"visible_activity_types": ["comment", "email_in"]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["visible_activity_types"], ["comment", "email_in"]
        )
        pref = UserStreamlinePreference.objects.get(user=self.user)
        self.assertEqual(pref.visible_activity_types, ["comment", "email_in"])

    def test_put_null_resets_to_defaults(self):
        UserStreamlinePreference.objects.create(
            user=self.user, visible_activity_types=["comment"]
        )
        resp = self._put({"visible_activity_types": None})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["visible_activity_types"])
        pref = UserStreamlinePreference.objects.get(user=self.user)
        self.assertIsNone(pref.visible_activity_types)

    def test_put_empty_list_persists_as_empty_not_null(self):
        # Empty list is a valid choice ("show nothing") and must round-trip.
        resp = self._put({"visible_activity_types": []})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["visible_activity_types"], [])

    def test_put_deduplicates_and_strips_blanks(self):
        resp = self._put({
            "visible_activity_types": [" comment ", "comment", "", "email_in"]
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["visible_activity_types"], ["comment", "email_in"]
        )

    def test_put_replaces_existing_value(self):
        UserStreamlinePreference.objects.create(
            user=self.user, visible_activity_types=["old"]
        )
        resp = self._put({"visible_activity_types": ["new"]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["visible_activity_types"], ["new"])

    def test_requires_authentication(self):
        self.client.logout()
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, [401, 403])
        resp = self._put({"visible_activity_types": []})
        self.assertIn(resp.status_code, [401, 403])


class StreamlineToolsAPITest(TestCase):
    """Verify the /streamline/tools endpoint exposes category metadata."""

    URL = "/api/v1/streamline/tools"

    def setUp(self):
        self.user = User.objects.create_user(email="t@example.com", password="pass")
        self.client.login(username="t@example.com", password="pass")

    def test_tools_response_includes_category_and_default_visibility(self):
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        tools = resp.json()
        self.assertGreater(len(tools), 0)
        for tool in tools:
            self.assertIn("category", tool)
            self.assertIn("default_visibility", tool)
            self.assertIn(
                tool["category"],
                {"communication", "task", "commerce", "system", "ai", "meta"},
            )
            self.assertIn(tool["default_visibility"], {"important", "secondary"})

    def test_known_tools_have_expected_categories(self):
        resp = self.client.get(self.URL)
        by_type = {t["activity_type"]: t for t in resp.json()}
        # Communication/important
        self.assertEqual(by_type["comment"]["category"], "communication")
        self.assertEqual(by_type["comment"]["default_visibility"], "important")
        self.assertEqual(by_type["email_in"]["category"], "communication")
        # System/secondary (defaults — noise)
        self.assertEqual(by_type["system_note"]["category"], "system")
        self.assertEqual(by_type["system_note"]["default_visibility"], "secondary")
        self.assertEqual(by_type["tag_added"]["default_visibility"], "secondary")
        # AI
        self.assertEqual(by_type["ai_summary"]["category"], "ai")
