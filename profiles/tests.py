from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from interactions.models import ContactRequest

from .forms import LifestyleForm, SearchForm
from .models import CriterionWeight, LifestylePreference, SearchPreference

User = get_user_model()


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("p@example.com", "Sup3r-secret-pass", first_name="Петро", last_name="Т")
        self.client.force_login(self.user)

    def test_edit_profile(self):
        self.client.post(reverse("profiles:edit"), {"display_name": "Петрик", "city": "Львів", "occupation": "Студент",
                                                   "about": "Люблю тишу", "search_mode": "joint", "move_in_date": "2026-09-01",
                                                   "is_active_search": "on"})
        profile = self.user.profile
        profile.refresh_from_db()
        self.assertEqual((profile.display_name, profile.city, profile.move_in_date), ("Петрик", "Львів", date(2026, 9, 1)))

    def test_profile_requires_name(self):
        response = self.client.post(reverse("profiles:edit"), {"display_name": "", "search_mode": "joint"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "обов")

    def test_profile_photo_validation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad = SimpleUploadedFile("x.png", b"not-image", content_type="image/png")
        response = self.client.post(reverse("profiles:edit"), {"display_name": "П", "search_mode": "joint", "photo": bad})
        self.assertEqual(response.status_code, 200)

    def test_lifestyle_saved(self):
        self.client.post(reverse("profiles:lifestyle"), {"sleep_schedule": "early", "cleanliness": "5", "noise_level": "2",
                                                        "guests_frequency": "sometimes", "smoking": "no", "pets": "none",
                                                        "work_schedule": "study", "chores_attitude": "split"})
        life = LifestylePreference.objects.get(profile=self.user.profile)
        self.assertEqual((life.sleep_schedule, life.cleanliness, life.noise_level), ("early", 5, 2))

    def test_lifestyle_partial_allowed_and_scale_validated(self):
        self.assertTrue(LifestyleForm({}).is_valid())
        self.assertFalse(LifestyleForm({"cleanliness": "9"}).is_valid())

    def test_search_form_saves_weights_and_critical(self):
        data = {"city": "Львів", "district": "Франківський", "budget_min": "5000", "budget_max": "8000",
                "req_sleep": "early", "req_min_cleanliness": "4", "req_max_noise": "", "req_guests": "any",
                "req_smoking": "no_inside", "req_pets": "any", "req_chores": "any"}
        data.update({f"w_{k}": "3" for k in ["budget", "location", "move_in", "sleep", "cleanliness", "noise", "guests", "smoking", "pets", "chores"]})
        data.update({"w_budget": "5", "c_smoking": "on"})
        response = self.client.post(reverse("profiles:search"), data)
        self.assertRedirects(response, reverse("matching:recommendations"))
        search = SearchPreference.objects.get(profile=self.user.profile)
        self.assertEqual((search.budget_min, search.req_min_cleanliness, search.req_max_noise), (5000, 4, None))
        self.assertEqual(CriterionWeight.objects.get(profile=self.user.profile, criterion="budget").weight, 5)
        self.assertTrue(CriterionWeight.objects.get(profile=self.user.profile, criterion="smoking").is_critical)
        self.assertEqual(CriterionWeight.objects.filter(profile=self.user.profile).count(), 10)

    def test_search_form_budget_min_greater_than_max(self):
        data = {"budget_min": "9000", "budget_max": "5000", "req_sleep": "any", "req_guests": "any", "req_smoking": "any",
                "req_pets": "any", "req_chores": "any"}
        data.update({f"w_{k}": "3" for k in ["budget", "location", "move_in", "sleep", "cleanliness", "noise", "guests", "smoking", "pets", "chores"]})
        form = SearchForm(data, profile=self.user.profile)
        self.assertFalse(form.is_valid())

    def test_weight_out_of_range_rejected(self):
        data = {"req_sleep": "any", "req_guests": "any", "req_smoking": "any", "req_pets": "any", "req_chores": "any"}
        data.update({f"w_{k}": "9" for k in ["budget", "location", "move_in", "sleep", "cleanliness", "noise", "guests", "smoking", "pets", "chores"]})
        self.assertFalse(SearchForm(data, profile=self.user.profile).is_valid())

    def test_pages_render(self):
        for name in ["profiles:dashboard", "profiles:view", "profiles:edit", "profiles:lifestyle", "profiles:search",
                     "accounts:settings", "housing:create", "housing:mine", "interactions:list", "chat:list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_weights_table_is_scrollable_on_small_screens(self):
        self.assertContains(self.client.get(reverse("profiles:search")), 'class="table-scroll"')

    def test_home_is_public(self):
        self.client.logout()
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Знайдіть співмешканця")


import io  # noqa: E402
import tempfile  # noqa: E402

from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402
from django.test import override_settings  # noqa: E402

from chat.models import Message  # noqa: E402
from housing.models import HousingListing  # noqa: E402
from matching.services import get_recommendations  # noqa: E402

DEMO_DOMAIN = "@demo.roommate.local"


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="demo_media_"),
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeedDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", "--force", stdout=io.StringIO())

    def demo_users(self):
        return User.objects.filter(email__endswith=DEMO_DOMAIN)

    def test_creates_twenty_profiles_with_photos_and_data(self):
        self.assertEqual(self.demo_users().count(), 20)
        for user in self.demo_users():
            self.assertTrue(user.profile.photo, user.email)
            self.assertIn("демонстраційний профіль", user.profile.about)
            self.assertEqual(user.profile.weights.count(), 10)
            self.assertTrue(hasattr(user.profile, "lifestyle") and hasattr(user.profile, "search"))
        self.assertEqual(HousingListing.objects.count(), 6)
        self.assertTrue(all(l.photos.count() == 3 for l in HousingListing.objects.all()))
        self.assertTrue(all("вигадана адреса" in l.address for l in HousingListing.objects.all()))

    def test_is_idempotent(self):
        before = (User.objects.count(), HousingListing.objects.count(), Message.objects.count(), ContactRequest.objects.count())
        call_command("seed_demo", "--force", stdout=io.StringIO())
        after = (User.objects.count(), HousingListing.objects.count(), Message.objects.count(), ContactRequest.objects.count())
        self.assertEqual(before, after)
        self.assertEqual(sum(l.photos.count() for l in HousingListing.objects.all()), 18)

    def test_refuses_non_demo_database_without_force(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", verbosity=0)

    def test_purge_legacy_removes_only_old_test_accounts(self):
        User.objects.create_user("old.qa@example.test", "x12345678!", first_name="Старий", last_name="Т")
        User.objects.create_user("old2.run@example.test", "x12345678!", first_name="Старий2", last_name="Т")
        User.objects.create_user("real.person@example.com", "x12345678!", first_name="Реальний", last_name="Т")
        User.objects.create_superuser("admin.run@example.test", "x12345678!", first_name="Адмін", last_name="Т")
        call_command("seed_demo", "--force", "--purge-legacy", stdout=io.StringIO())
        emails = set(User.objects.values_list("email", flat=True))
        self.assertNotIn("old.qa@example.test", emails)
        self.assertNotIn("old2.run@example.test", emails)
        self.assertIn("real.person@example.com", emails)
        self.assertIn("admin.run@example.test", emails)  # адміністраторів не видаляємо
        self.assertEqual(self.demo_users().count(), 20)

    def test_reset_rebuilds_only_demo_accounts(self):
        User.objects.create_user("real.person@example.com", "x12345678!", first_name="Реальний", last_name="Т")
        call_command("seed_demo", "--force", "--reset", stdout=io.StringIO())
        self.assertTrue(User.objects.filter(email="real.person@example.com").exists())
        self.assertEqual(self.demo_users().count(), 20)

    def test_algorithm_gives_varied_reasoned_results(self):
        viewer = User.objects.get(email="andriy.koval" + DEMO_DOMAIN)
        results = get_recommendations(viewer)
        scores = [o.score for _, o in results if o.score is not None]
        self.assertGreaterEqual(len(scores), 15)
        self.assertGreater(max(scores) - min(scores), 30)
        self.assertTrue(any(o.has_critical_conflict for _, o in results))
        self.assertTrue(any(not o.has_critical_conflict and o.score and o.score >= 85 for _, o in results))
        strict = User.objects.get(email="anastasiia.boiko" + DEMO_DOMAIN)
        self.assertGreaterEqual(sum(o.has_critical_conflict for _, o in get_recommendations(strict)), 5)

    def test_chat_and_requests_are_ready_to_demonstrate(self):
        viewer = User.objects.get(email="andriy.koval" + DEMO_DOMAIN)
        self.client.force_login(viewer)
        response = self.client.get(reverse("chat:list"))
        self.assertEqual(len(response.context["conversations"]), 2)
        self.assertGreater(Message.objects.filter(read_at__isnull=True).exclude(sender=viewer).count(), 0)
        pending = ContactRequest.objects.filter(receiver=viewer, status="pending").count()
        self.assertEqual(pending, 2)
        self.assertContains(self.client.get(reverse("interactions:list")), "Прийняти")


class HeroTests(TestCase):
    """Hero: тексти демо-картки рендеряться на сервері, варіанти для ротації коректні, колір успадковується правильно."""

    def home(self):
        return self.client.get(reverse("home")).content.decode()

    def test_demo_card_texts_are_rendered_on_server(self):
        html = self.home()
        for text in ("Андрій", "Львів · студент", ">89%<", "Бюджет", "Чистота", "Режим сну", "Гості", "Приклад формату результату"):
            self.assertIn(text, html)
        self.assertEqual(html.count("data-label"), 4)
        self.assertEqual(html.count("data-value"), 4)

    def test_variants_json_is_valid_and_first_matches_server_render(self):
        import json
        import re
        html = self.home()
        data = json.loads(re.search(r'id="demo-variants">(.*?)</script>', html, re.S).group(1))
        self.assertGreaterEqual(len(data), 3)
        for v in data:
            self.assertTrue({"initial", "name", "meta", "score", "grad", "rows", "note"} <= set(v))
            self.assertEqual(len(v["rows"]), 4)
            self.assertTrue(0 <= v["score"] <= 100)
        self.assertEqual(data[0]["name"], "Андрій")
        self.assertIn(f">{data[0]['score']}%<", html)
        self.assertEqual(len({v["name"] for v in data}), len(data))

    def test_demo_card_does_not_inherit_white_hero_text(self):
        """Раніше .hero{color:#fff} робило текст білим на білій картці."""
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/main.css").read_text(encoding="utf-8")
        rule = css.split(".demo{", 1)[1].split("}", 1)[0]
        self.assertIn("color:var(--ink)", rule)

    def test_rotation_script_respects_reduced_motion_and_has_controls(self):
        from pathlib import Path
        from django.conf import settings
        js = (Path(settings.BASE_DIR) / "static/js/main.js").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("demo-variants", js)
        self.assertIn("card.dataset.ready", js)  # ініціалізація ідемпотентна
        self.assertIn('aria-pressed', js)
        self.assertContains(self.client.get(reverse("home")), 'id="demo-dots"')
