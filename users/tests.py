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
