import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from interactions.models import ContactRequest

from .models import HousingListing, HousingPhoto

User = get_user_model()


def image_file(name="a.png", fmt="PNG", size=(20, 20)):
    buf = io.BytesIO()
    Image.new("RGB", size, "teal").save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


VALID = {"title": "Кімната у центрі", "city": "Львів", "district": "Франківський", "address": "вул. Тестова, 1",
         "price_per_person": 6500, "rooms": 2, "free_places": 1, "description": "Світла квартира", "is_active": "on"}


@override_settings(MEDIA_ROOT="/tmp/roommate_test_media")
class HousingTests(TestCase):
    def setUp(self):
        mk = lambda e, n: User.objects.create_user(e, "Sup3r-secret-pass", first_name=n, last_name="Т")  # noqa: E731
        self.owner, self.guest = mk("o@example.com", "Власник"), mk("g@example.com", "Гість")

    def create(self, **extra):
        self.client.force_login(self.owner)
        return self.client.post(reverse("housing:create"), {**VALID, **extra})

    def test_create_listing_with_photos(self):
        response = self.create(photos=[image_file("1.png"), image_file("2.png")])
        listing = HousingListing.objects.get()
        self.assertRedirects(response, reverse("housing:detail", args=[listing.pk]))
        self.assertEqual((listing.owner, listing.photos.count()), (self.owner, 2))

    def test_invalid_extension_and_fake_image_rejected(self):
        bad = SimpleUploadedFile("evil.exe", b"MZ...", content_type="application/octet-stream")
        fake = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        for f in (bad, fake):
            response = self.create(photos=[f])
            self.assertEqual(response.status_code, 200)
        self.assertFalse(HousingListing.objects.exists())

    @override_settings(MAX_IMAGE_SIZE=100)
    def test_too_large_image_rejected(self):
        response = self.create(photos=[image_file(size=(300, 300))])
        self.assertContains(response, "завеликий")

    @override_settings(MAX_LISTING_PHOTOS=1)
    def test_photo_count_limit(self):
        response = self.create(photos=[image_file("1.png"), image_file("2.png")])
        self.assertContains(response, "не більше")

    def test_validation_price_and_places(self):
        self.assertEqual(self.create(price_per_person=0).status_code, 200)
        self.assertFalse(HousingListing.objects.exists())

    def test_exact_address_hidden_from_public_but_visible_to_owner(self):
        self.create()
        listing = HousingListing.objects.get()
        url = reverse("housing:detail", args=[listing.pk])
        self.assertContains(self.client.get(url), "вул. Тестова, 1")
        self.client.force_login(self.guest)
        self.assertNotContains(self.client.get(url), "вул. Тестова, 1")

    def test_address_visible_after_accepted_request(self):
        self.create()
        listing = HousingListing.objects.get()
        ContactRequest.objects.create(sender=self.guest, receiver=self.owner, housing=listing, status="accepted")
        self.client.force_login(self.guest)
        self.assertContains(self.client.get(reverse("housing:detail", args=[listing.pk])), "вул. Тестова, 1")

    def test_address_visible_after_request_from_profile_without_listing(self):
        """D-03: запит із профілю кандидата (без прив’язки до оголошення) теж відкриває адресу після прийняття."""
        self.create()
        listing = HousingListing.objects.get()
        ContactRequest.objects.create(sender=self.guest, receiver=self.owner, status="accepted")
        self.client.force_login(self.guest)
        self.assertContains(self.client.get(reverse("housing:detail", args=[listing.pk])), "вул. Тестова, 1")

    def test_address_visible_when_owner_initiated_accepted_request(self):
        self.create()
        listing = HousingListing.objects.get()
        ContactRequest.objects.create(sender=self.owner, receiver=self.guest, status="accepted")
        self.client.force_login(self.guest)
        self.assertContains(self.client.get(reverse("housing:detail", args=[listing.pk])), "вул. Тестова, 1")

    def test_address_hidden_for_pending_declined_or_blocked(self):
        from interactions.models import UserBlock
        self.create()
        listing = HousingListing.objects.get()
        url = reverse("housing:detail", args=[listing.pk])
        self.client.force_login(self.guest)
        for status in ("pending", "declined", "cancelled"):
            ContactRequest.objects.all().delete()
            ContactRequest.objects.create(sender=self.guest, receiver=self.owner, status=status)
            self.assertNotContains(self.client.get(url), "вул. Тестова, 1", msg_prefix=status)
        ContactRequest.objects.all().delete()
        ContactRequest.objects.create(sender=self.guest, receiver=self.owner, status="accepted")
        UserBlock.objects.create(blocker=self.owner, blocked=self.guest)
        self.assertNotContains(self.client.get(url), "вул. Тестова, 1")

    def test_detail_layout_collapses_on_mobile_via_css_class(self):
        """Інлайн-стиль grid-template-columns перебивав адаптивний CSS на телефонах."""
        self.create()
        self.client.force_login(self.guest)
        page = self.client.get(reverse("housing:detail", args=[HousingListing.objects.get().pk]))
        self.assertContains(page, "layout-main-side")
        self.assertNotContains(page, 'style="grid-template-columns')

    def test_only_owner_can_edit_delete_toggle(self):
        self.create()
        listing = HousingListing.objects.get()
        self.client.force_login(self.guest)
        self.assertEqual(self.client.get(reverse("housing:edit", args=[listing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("housing:delete", args=[listing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("housing:toggle", args=[listing.pk])).status_code, 404)
        self.assertTrue(HousingListing.objects.filter(pk=listing.pk).exists())

    def test_owner_edit_toggle_delete(self):
        self.create()
        listing = HousingListing.objects.get()
        self.client.force_login(self.owner)
        self.client.post(reverse("housing:edit", args=[listing.pk]), {**VALID, "title": "Нова назва"})
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Нова назва")
        self.client.post(reverse("housing:toggle", args=[listing.pk]))
        listing.refresh_from_db()
        self.assertFalse(listing.is_active)
        self.client.post(reverse("housing:delete", args=[listing.pk]))
        self.assertFalse(HousingListing.objects.exists())

    def test_inactive_and_hidden_not_listed_or_viewable(self):
        self.create()
        listing = HousingListing.objects.get()
        self.client.force_login(self.guest)
        self.assertContains(self.client.get(reverse("housing:list")), "Кімната у центрі")
        for field in ("is_active", "is_hidden"):
            HousingListing.objects.filter(pk=listing.pk).update(is_active=True, is_hidden=False)
            HousingListing.objects.filter(pk=listing.pk).update(**{field: field == "is_hidden"} if field == "is_hidden" else {field: False})
            self.assertNotContains(self.client.get(reverse("housing:list")), "Кімната у центрі")
            self.assertEqual(self.client.get(reverse("housing:detail", args=[listing.pk])).status_code, 404)

    def test_filters(self):
        # Регістронезалежність кирилиці забезпечує MySQL (utf8mb4); SQLite порівнює без урахування регістру лише ASCII.
        self.create()
        self.client.force_login(self.guest)
        self.assertContains(self.client.get(reverse("housing:list"), {"city": "Льв"}), "Кімната у центрі")
        self.assertNotContains(self.client.get(reverse("housing:list"), {"max_price": 1000}), "Кімната у центрі")

    def test_photo_delete_only_by_owner(self):
        self.create(photos=[image_file()])
        photo = HousingPhoto.objects.get()
        self.client.force_login(self.guest)
        self.assertEqual(self.client.post(reverse("housing:photo_delete", args=[photo.pk])).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse("housing:photo_delete", args=[photo.pk]))
        self.assertFalse(HousingPhoto.objects.exists())
