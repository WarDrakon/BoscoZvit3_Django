from django.test import TestCase
from django.urls import reverse

from .forms import RegisterForm
from .models import User


class UserModelTests(TestCase):
    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user("Test@Example.COM", "S3cure-pass!", first_name="Т", last_name="К")
        self.assertEqual(user.email, "test@example.com")
        self.assertNotEqual(user.password, "S3cure-pass!")
        self.assertTrue(user.check_password("S3cure-pass!"))

    def test_profile_created_automatically(self):
        user = User.objects.create_user("a@example.com", "S3cure-pass!", first_name="Андрій", last_name="К")
        self.assertEqual(user.profile.display_name, "Андрій")


class AuthFlowTests(TestCase):
    def setUp(self):
        self.data = {"first_name": "Андрій", "last_name": "Коваль", "email": "andriy@example.com",
                     "password1": "Sup3r-secret-pass", "password2": "Sup3r-secret-pass"}

    def test_register_logs_in_and_redirects_to_dashboard(self):
        response = self.client.post(reverse("accounts:register"), self.data)
        self.assertRedirects(response, reverse("profiles:dashboard"))
        self.assertTrue(User.objects.filter(email="andriy@example.com").exists())

    def test_register_password_mismatch(self):
        self.data["password2"] = "other"
        form = RegisterForm(self.data)
        self.assertFalse(form.is_valid())
        self.assertIn("Паролі не збігаються.", form.errors["password2"])

    def test_register_duplicate_email_case_insensitive(self):
        User.objects.create_user("andriy@example.com", "x12345678!", first_name="А", last_name="Б")
        self.data["email"] = "ANDRIY@example.com"
        self.assertFalse(RegisterForm(self.data).is_valid())

    def test_weak_password_rejected(self):
        self.data.update(password1="12345678", password2="12345678")
        self.assertFalse(RegisterForm(self.data).is_valid())

    def test_login_with_email_and_logout(self):
        User.objects.create_user("andriy@example.com", "Sup3r-secret-pass", first_name="А", last_name="Б")
        response = self.client.post(reverse("accounts:login"), {"username": "Andriy@Example.com", "password": "Sup3r-secret-pass"})
        self.assertRedirects(response, reverse("profiles:dashboard"))
        self.assertEqual(self.client.get(reverse("profiles:dashboard")).status_code, 200)
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("profiles:dashboard")).status_code, 302)

    def test_login_wrong_password_shows_ukrainian_error(self):
        User.objects.create_user("andriy@example.com", "Sup3r-secret-pass", first_name="А", last_name="Б")
        response = self.client.post(reverse("accounts:login"), {"username": "andriy@example.com", "password": "bad"})
        self.assertContains(response, "Невірна пошта або пароль")

    def test_protected_pages_redirect_anonymous(self):
        for name in ["profiles:dashboard", "matching:recommendations", "housing:list", "chat:list", "interactions:list"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("accounts:login"), response["Location"])

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)


class AccountManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u@example.com", "Sup3r-secret-pass", first_name="У", last_name="Ж")
        self.client.force_login(self.user)

    def test_change_name_and_email(self):
        self.client.post(reverse("accounts:settings"), {"first_name": "Нове", "last_name": "Ім’я", "email": "new@example.com"})
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email), ("Нове", "new@example.com"))

    def test_deactivate_requires_correct_password(self):
        self.client.post(reverse("accounts:deactivate"), {"password": "wrong"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.client.post(reverse("accounts:deactivate"), {"password": "Sup3r-secret-pass"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.profile.is_active_search)

    def test_deactivated_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.client.logout()
        response = self.client.post(reverse("accounts:login"), {"username": "u@example.com", "password": "Sup3r-secret-pass"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "деактивовано")
        self.assertNotContains(response, "Невірна пошта")

    def test_deactivated_account_with_wrong_password_does_not_reveal_status(self):
        self.user.is_active = False
        self.user.save()
        self.client.logout()
        response = self.client.post(reverse("accounts:login"), {"username": "u@example.com", "password": "bad"})
        self.assertContains(response, "Невірна пошта")
        self.assertNotContains(response, "деактивовано")

    def test_existing_session_stops_working_after_deactivation(self):
        self.assertEqual(self.client.get(reverse("profiles:dashboard")).status_code, 200)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("profiles:dashboard")).status_code, 302)

    def test_delete_account_removes_user_and_profile(self):
        self.client.post(reverse("accounts:delete"), {"password": "Sup3r-secret-pass"})
        self.assertFalse(User.objects.filter(email="u@example.com").exists())

    def test_password_reset_sends_email(self):
        from django.core import mail
        self.client.logout()
        self.client.post(reverse("accounts:password_reset"), {"email": "u@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)
