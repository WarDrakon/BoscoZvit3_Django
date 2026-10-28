from decimal import Decimal

from django.contrib.auth.models import Group
from django.template import Context, Template
from django.test import TestCase

from accounts.models import User
from chat.models import Conversation
from housing.models import HousingListing


def render(template_str, **ctx):
    return Template("{% load roommate_tags %}" + template_str).render(Context(ctx))


class ScoreTagsTests(TestCase):
    def test_score_level_thresholds(self):
        self.assertEqual(render("{% score_level s %}", s=Decimal("75")), "")
        self.assertEqual(render("{% score_level s %}", s=Decimal("74.9")), "mid")
        self.assertEqual(render("{% score_level s %}", s=50), "mid")
        self.assertEqual(render("{% score_level s %}", s=49), "low")

    def test_score_ring_with_score(self):
        html = render('{% score_ring s "lg" %}', s=Decimal("42"))
        self.assertIn('class="ring lg low"', html)
        self.assertIn("--p:42", html)
        self.assertIn("42%", html)

    def test_score_ring_without_score(self):
        html = render("{% score_ring s %}", s=None)
        self.assertIn('class="ring"', html)
        self.assertIn("—", html)


class AbsoluteUrlAndMigrationTests(TestCase):
    def test_get_absolute_url(self):
        owner = User.objects.create_user("o@example.com", "Test-pass-123", first_name="Олена", last_name="Мельник")
        other = User.objects.create_user("p@example.com", "Test-pass-123", first_name="Андрій", last_name="Коваль")
        listing = HousingListing.objects.create(owner=owner, title="Кімната", city="Львів", price_per_person=5000,
                                                description="Опис")
        self.assertEqual(listing.get_absolute_url(), f"/housing/{listing.pk}/")
        self.assertEqual(owner.profile.get_absolute_url(), f"/people/{owner.profile.pk}/")
        conversation = Conversation.objects.get_or_create_between(owner, other)
        self.assertEqual(conversation.get_absolute_url(), f"/chat/{conversation.pk}/")

    def test_data_migration_created_moderators_group(self):
        self.assertTrue(Group.objects.filter(name="Модератори").exists())
