from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chat.models import Conversation

from .models import ContactRequest, Report, UserBlock

User = get_user_model()


def make_user(email, name):
    return User.objects.create_user(email, "Sup3r-secret-pass", first_name=name, last_name="Т")


class ContactRequestTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@example.com", "Аліса"), make_user("b@example.com", "Богдан")

    def send(self, sender, receiver, **extra):
        self.client.force_login(sender)
        return self.client.post(reverse("interactions:send", args=[receiver.pk]), {"message": "Привіт!", **extra})

    def test_full_flow_request_accept_creates_conversation(self):
        self.send(self.a, self.b)
        contact = ContactRequest.objects.get()
        self.assertEqual(contact.status, "pending")
        self.client.force_login(self.b)
        response = self.client.post(reverse("interactions:respond", args=[contact.pk, "accept"]))
        contact.refresh_from_db()
        self.assertEqual(contact.status, "accepted")
        conversation = Conversation.objects.get()
        self.assertRedirects(response, reverse("chat:detail", args=[conversation.pk]))
        self.assertEqual({conversation.user_one, conversation.user_two}, {self.a, self.b})

    def test_decline(self):
        self.send(self.a, self.b)
        contact = ContactRequest.objects.get()
        self.client.force_login(self.b)
        self.client.post(reverse("interactions:respond", args=[contact.pk, "decline"]))
        contact.refresh_from_db()
        self.assertEqual(contact.status, "declined")
        self.assertFalse(Conversation.objects.exists())

    def test_only_receiver_can_respond(self):
        self.send(self.a, self.b)
        contact = ContactRequest.objects.get()
        self.client.force_login(self.a)
        response = self.client.post(reverse("interactions:respond", args=[contact.pk, "accept"]))
        self.assertEqual(response.status_code, 404)
        stranger = make_user("c@example.com", "Сторонній")
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(reverse("interactions:respond", args=[contact.pk, "accept"])).status_code, 404)

    def test_cannot_send_to_self(self):
        self.send(self.a, self.a)
        self.assertFalse(ContactRequest.objects.exists())

    def test_no_duplicate_pending_requests_either_direction(self):
        self.send(self.a, self.b)
        self.send(self.a, self.b)
        self.send(self.b, self.a)
        self.assertEqual(ContactRequest.objects.count(), 1)

    def test_cannot_send_to_blocked_user(self):
        UserBlock.objects.create(blocker=self.b, blocked=self.a)
        self.send(self.a, self.b)
        self.assertFalse(ContactRequest.objects.exists())

    def test_respond_requires_post(self):
        self.send(self.a, self.b)
        contact = ContactRequest.objects.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse("interactions:respond", args=[contact.pk, "accept"])).status_code, 405)

    def test_cancel_by_sender(self):
        self.send(self.a, self.b)
        contact = ContactRequest.objects.get()
        self.client.force_login(self.a)
        self.client.post(reverse("interactions:cancel", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertEqual(contact.status, "cancelled")


class BlockAndReportTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@example.com", "Аліса"), make_user("b@example.com", "Богдан")

    def test_block_cancels_pending_and_unblock(self):
        ContactRequest.objects.create(sender=self.b, receiver=self.a)
        self.client.force_login(self.a)
        self.client.post(reverse("interactions:block", args=[self.b.pk]))
        self.assertTrue(UserBlock.objects.filter(blocker=self.a, blocked=self.b).exists())
        self.assertEqual(ContactRequest.objects.get().status, "cancelled")
        self.client.post(reverse("interactions:unblock", args=[self.b.pk]))
        self.assertFalse(UserBlock.objects.exists())

    def test_cannot_block_self(self):
        self.client.force_login(self.a)
        self.client.post(reverse("interactions:block", args=[self.a.pk]))
        self.assertFalse(UserBlock.objects.exists())

    def test_report_user(self):
        self.client.force_login(self.a)
        self.client.post(reverse("interactions:report_user", args=[self.b.pk]), {"reason": "spam", "description": "Реклама"})
        report = Report.objects.get()
        self.assertEqual((report.reporter, report.reported_user, report.status), (self.a, self.b, "new"))

    def test_block_page_requires_login(self):
        self.assertEqual(self.client.get(reverse("interactions:blocks")).status_code, 302)
