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


class RegistrationPasswordTests(TestCase):
    """Сервер остаточно перевіряє пароль валідаторами Django; повідомлення українською."""

    def setUp(self):
        self.base = {"first_name": "Андрій", "last_name": "Коваль", "email": "andriy@example.com"}

    def form(self, password, confirm=None):
        return RegisterForm({**self.base, "password1": password, "password2": password if confirm is None else confirm})

    def errors(self, password):
        form = self.form(password)
        self.assertFalse(form.is_valid(), password)
        return " ".join(form.errors["password1"])

    def test_strong_password_accepted(self):
        for password in ("Sup3r-secret-pass", "mV7#qRt9$wLp2", "Zx9!kLm2"):
            self.assertTrue(self.form(password).is_valid(), password)

    def test_minimum_length_8(self):
        self.assertIn("8", self.errors("Ab1!xyz"))

    def test_each_character_class_is_required_with_ukrainian_message(self):
        self.assertIn("малу літеру", self.errors("ABCDEF1!ZX"))
        self.assertIn("велику літеру", self.errors("abcdef1!zx"))
        self.assertIn("цифру", self.errors("Abcdef!ghx"))
        self.assertIn("спеціальний символ", self.errors("Abcdef1ghx"))

    def test_all_missing_classes_reported_at_once(self):
        text = self.errors("abcdefgh")
        for part in ("велику літеру", "цифру", "спеціальний символ"):
            self.assertIn(part, text)

    def test_common_and_obvious_passwords_rejected_even_if_complex(self):
        for password in ("Password1!", "P@ssw0rd", "Qwerty123!", "Iloveyou1!", "Welcome1!", "123Password!", "Aa1!Aa1!Aa1!", "Qwertyuiop1!"):
            self.assertIn("очевидний", self.errors(password), password)

    def test_numeric_and_similar_to_user_data_rejected(self):
        self.assertTrue(self.errors("12345678"))
        self.assertIn("схожий", self.errors("Andriy@example.com1!"))

    def test_mismatch_reported(self):
        form = self.form("Sup3r-secret-pass", "Sup3r-secret-pasZ")
        self.assertFalse(form.is_valid())
        self.assertIn("Паролі не збігаються.", form.errors["password2"])

    def test_invalid_registration_does_not_create_user_and_shows_reason(self):
        response = self.client.post(reverse("accounts:register"), {**self.base, "password1": "Password1!", "password2": "Password1!"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "очевидний")
        self.assertFalse(User.objects.filter(email="andriy@example.com").exists())

    def test_register_page_has_strength_ui_hooks(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertContains(response, 'data-pw="main"')
        self.assertContains(response, 'data-pw="confirm"')
        self.assertContains(response, "js/password.js")
        self.assertContains(response, reverse("accounts:password_check"))

    def test_other_password_flows_unchanged(self):
        user = User.objects.create_user("c@example.com", "Sup3r-secret-pass", first_name="К", last_name="Л")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "Sup3r-secret-pass", "new_password1": "longpasswordwithoutdigits", "new_password2": "longpasswordwithoutdigits"})
        self.assertEqual(response.status_code, 302)


class PasswordCheckEndpointTests(TestCase):
    def check(self, **data):
        return self.client.post(reverse("accounts:password_check"), data)

    def test_reports_codes_and_ukrainian_messages(self):
        body = self.check(password="Password1!").json()
        self.assertFalse(body["ok"])
        self.assertIn("password_obvious", body["codes"])
        self.assertTrue(all(any("а" <= c.lower() <= "я" or c in "іїєґ" for c in m) for m in body["messages"]))

    def test_strong_and_empty_ok(self):
        self.assertEqual(self.check(password="mV7#qRt9$wLp2").json(), {"ok": True, "codes": [], "messages": []})
        self.assertTrue(self.check(password="").json()["ok"])

    def test_similarity_uses_submitted_data(self):
        self.assertIn("password_too_similar", self.check(password="Andriykoval1!", email="andriykoval@example.com").json()["codes"])

    def test_post_only_and_not_cached(self):
        self.assertEqual(self.client.get(reverse("accounts:password_check")).status_code, 405)
        self.assertIn("no-store", self.check(password="x")["Cache-Control"])


from datetime import date, timedelta  # noqa: E402
from io import StringIO  # noqa: E402

from django.core.management import call_command  # noqa: E402

from config.person_validators import NAME_MAX, birth_date_problem, name_problem  # noqa: E402


def years_ago(years, days=0):
    today = date.today()
    try:
        base = today.replace(year=today.year - years)
    except ValueError:
        base = today.replace(year=today.year - years, day=28)
    return base + timedelta(days=days)


class NameValidationTests(TestCase):
    """Ім’я та прізвище: 2–50 символів; не одна літера, не цифри, не лише пробіли."""

    def reg(self, **over):
        data = {"first_name": "Андрій", "last_name": "Коваль", "email": "andriy@example.com",
                "password1": "Sup3r-secret-pass", "password2": "Sup3r-secret-pass", **over}
        return RegisterForm(data)

    def test_valid_names_accepted_and_whitespace_normalized(self):
        for first, last in (("Іван", "Ян"), ("Анна-Марія", "Д’Артаньян"), ("Марія  Луїза", "Коваль-Шевченко"), ("Ан", "Бо")):
            self.assertTrue(self.reg(first_name=first, last_name=last).is_valid(), (first, last))
        form = self.reg(first_name="  Марія   Луїза ")
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["first_name"], "Марія Луїза")

    def test_invalid_names_rejected_with_ukrainian_reason(self):
        cases = {"А": "щонайменше 2", "   ": "порожнім", "12": "цифр", "123 456": "цифр", "Іван3": "лише літери", "Ан@": "лише літери",
                 "-Ан": "починатися", "А-": "дві літери", "я" * (NAME_MAX + 1): "довшим за 50"}
        for value, part in cases.items():
            for field in ("first_name", "last_name"):
                form = self.reg(**{field: value})
                self.assertFalse(form.is_valid(), (field, value))
                self.assertIn(part, " ".join(form.errors[field]), (field, value))

    def test_boundary_lengths(self):
        self.assertTrue(self.reg(first_name="а" * NAME_MAX).is_valid())
        self.assertFalse(self.reg(first_name="а" * (NAME_MAX + 1)).is_valid())

    def test_invalid_registration_creates_nothing(self):
        response = self.client.post(reverse("accounts:register"), {
            "first_name": "А", "last_name": "123", "email": "x@example.com", "password1": "Sup3r-secret-pass", "password2": "Sup3r-secret-pass"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "щонайменше 2")
        self.assertFalse(User.objects.filter(email="x@example.com").exists())

    def test_account_settings_form_validates_names(self):
        user = User.objects.create_user("a@example.com", "Sup3r-secret-pass", first_name="Андрій", last_name="Коваль")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:settings"), {"first_name": "А", "last_name": "Коваль", "email": "a@example.com"})
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Андрій")
        ok = self.client.post(reverse("accounts:settings"), {"first_name": " Олег  ", "last_name": "Коваль", "email": "a@example.com"})
        self.assertEqual(ok.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Олег")

    def test_pages_expose_live_validation_hooks(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertContains(response, 'data-validate="name"')
        self.assertContains(response, 'data-validate="birth-date"')
        self.assertContains(response, "js/validation.js")


class BirthDateRangeTests(TestCase):
    def reg(self, birth):
        return RegisterForm({"first_name": "Андрій", "last_name": "Коваль", "email": "andriy@example.com", "birth_date": birth,
                             "password1": "Sup3r-secret-pass", "password2": "Sup3r-secret-pass"})

    def test_age_between_18_and_100_inclusive(self):
        for birth in (years_ago(18), years_ago(30), years_ago(100)):
            self.assertTrue(self.reg(birth.isoformat()).is_valid(), birth)
        self.assertTrue(self.reg("").is_valid())  # поле необов’язкове

    def test_future_underage_and_unrealistic_rejected(self):
        cases = {(date.today() + timedelta(days=1)).isoformat(): "майбутньому", years_ago(18, days=1).isoformat(): "повнолітнім",
                 years_ago(101).isoformat(): "100", "1000-01-01": "100", "2000-02-31": "", "не-дата": ""}
        for value, part in cases.items():
            form = self.reg(value)
            self.assertFalse(form.is_valid(), value)
            self.assertIn(part, " ".join(form.errors["birth_date"]), value)

    def test_html_bounds_match_rules(self):
        form = self.reg("")
        attrs = form.fields["birth_date"].widget.attrs
        self.assertEqual(attrs["max"], years_ago(18).isoformat())
        self.assertEqual(attrs["min"], (years_ago(101) + timedelta(days=1)).isoformat())
        self.assertIsNone(birth_date_problem(date.fromisoformat(attrs["min"])))
        self.assertIsNone(birth_date_problem(date.fromisoformat(attrs["max"])))


class ExistingDataFixTests(TestCase):
    def setUp(self):
        self.ok = User.objects.create_user("ok@example.com", "Sup3r-secret-pass", first_name="Олена", last_name="Мельник")
        self.bad = User.objects.create_user("bad@example.com", "Sup3r-secret-pass", first_name="Я", last_name="12")  # create_user не валідує
        self.spaced = User.objects.create_user("sp@example.com", "Sup3r-secret-pass", first_name="  Марія   Луїза ", last_name="Коваль")
        for user, birth in ((self.ok, years_ago(25)), (self.bad, date.today() + timedelta(days=30)), (self.spaced, years_ago(150))):
            user.profile.birth_date = birth
            user.profile.save()
        self.bad.profile.display_name = "7"
        self.bad.profile.save()
        self.bad.first_name = "Я"
        self.bad.save()

    def run_cmd(self, *args):
        out = StringIO()
        call_command("fix_user_data", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        before = list(User.objects.values_list("pk", "first_name", "last_name"))
        text = self.run_cmd()
        self.assertIn("нічого не змінено", text)
        self.assertEqual(before, list(User.objects.values_list("pk", "first_name", "last_name")))
        self.bad.profile.refresh_from_db()
        self.assertIsNotNone(self.bad.profile.birth_date)

    def test_apply_fixes_safely_and_never_deletes(self):
        count = User.objects.count()
        text = self.run_cmd("--apply")
        self.assertEqual(User.objects.count(), count)
        self.ok.refresh_from_db(); self.bad.refresh_from_db(); self.spaced.refresh_from_db()
        self.assertEqual(self.ok.profile.birth_date, years_ago(25))          # коректні дані не чіпаємо
        self.assertEqual(self.spaced.first_name, "Марія Луїза")              # лише зайві пробіли
        self.assertIsNone(self.spaced.profile.birth_date)                    # вік 150 → «Вік не вказано», нічого не вигадано
        self.assertEqual(self.spaced.profile.age_label, "Вік не вказано")
        self.assertIsNone(self.bad.profile.birth_date)                       # дата в майбутньому
        self.assertEqual((self.bad.first_name, self.bad.last_name), ("Я", "12"))  # неможливо вгадати: лише позначка
        self.assertEqual(self.bad.profile.display_name, "7")                 # ім’я з акаунта теж некоректне — не підміняємо
        self.assertIn("потребує ручного виправлення", text)

    def test_invalid_public_name_replaced_by_valid_account_name(self):
        self.ok.profile.display_name = "1"
        self.ok.profile.save()
        self.run_cmd("--apply")
        self.ok.profile.refresh_from_db()
        self.assertEqual(self.ok.profile.display_name, "Олена")

    def test_admin_shows_age_and_data_check(self):
        admin = User.objects.create_superuser("root@example.com", "Sup3r-secret-pass", first_name="Адмін", last_name="Адмінко")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "25 років")
        self.assertContains(response, "Вік не вказано")
        self.assertContains(response, "Потрібне виправлення")
        self.assertEqual(self.client.get(reverse("admin:profiles_profile_changelist")).status_code, 200)

    def test_name_problem_helpers(self):
        self.assertIsNone(name_problem("Іван"))
        self.assertIn("щонайменше", name_problem("І"))
