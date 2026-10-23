from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from interactions.models import UserBlock

from .models import Conversation, Message

User = get_user_model()


class ChatTests(TestCase):
    def setUp(self):
        mk = lambda e, n: User.objects.create_user(e, "Sup3r-secret-pass", first_name=n, last_name="Т")  # noqa: E731
        self.a, self.b, self.c = mk("a@example.com", "А"), mk("b@example.com", "Б"), mk("c@example.com", "С")
        self.conv = Conversation.objects.get_or_create_between(self.b, self.a)

    def post(self, user, text, conv=None):
        self.client.force_login(user)
        return self.client.post(reverse("chat:send", args=[(conv or self.conv).pk]), data={"text": text},
                                content_type="application/json")

    def test_pair_is_unique_and_ordered(self):
        again = Conversation.objects.get_or_create_between(self.a, self.b)
        self.assertEqual(again.pk, self.conv.pk)
        self.assertLess(self.conv.user_one_id, self.conv.user_two_id)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_send_message_saved_in_db(self):
        response = self.post(self.a, "Привіт!")
        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertEqual((message.text, message.sender), ("Привіт!", self.a))
        self.assertIsNone(message.read_at)

    def test_receiver_gets_new_messages_and_marks_read(self):
        self.post(self.a, "Привіт!")
        self.client.force_login(self.b)
        data = self.client.get(reverse("chat:messages", args=[self.conv.pk]), {"after": 0}).json()
        self.assertEqual([m["text"] for m in data["messages"]], ["Привіт!"])
        self.assertFalse(data["messages"][0]["mine"])
        self.assertIsNotNone(Message.objects.get().read_at)
        # відправник бачить, що повідомлення прочитано
        self.client.force_login(self.a)
        data = self.client.get(reverse("chat:messages", args=[self.conv.pk])).json()
        self.assertEqual(data["read_ids"], [Message.objects.get().pk])

    def test_after_parameter_returns_only_new(self):
        self.post(self.a, "1")
        first = Message.objects.get().pk
        self.post(self.a, "2")
        self.client.force_login(self.b)
        data = self.client.get(reverse("chat:messages", args=[self.conv.pk]), {"after": first}).json()
        self.assertEqual([m["text"] for m in data["messages"]], ["2"])

    def test_stranger_cannot_read_or_write_by_changing_id(self):
        self.post(self.a, "секрет")
        self.client.force_login(self.c)
        for name in ("chat:detail", "chat:messages"):
            self.assertEqual(self.client.get(reverse(name, args=[self.conv.pk])).status_code, 404, name)
        self.assertEqual(self.post(self.c, "хакер").status_code, 404)
        self.assertEqual(Message.objects.count(), 1)

    def test_conversation_list_shows_only_own(self):
        other = Conversation.objects.get_or_create_between(self.b, self.c)
        self.client.force_login(self.a)
        response = self.client.get(reverse("chat:list"))
        self.assertContains(response, reverse("chat:detail", args=[self.conv.pk]))
        self.assertNotContains(response, reverse("chat:detail", args=[other.pk]))

    def test_empty_and_too_long_messages_rejected(self):
        self.assertEqual(self.post(self.a, "   ").status_code, 400)
        self.assertEqual(self.post(self.a, "я" * 2001).status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_blocked_user_cannot_send(self):
        UserBlock.objects.create(blocker=self.b, blocked=self.a)
        self.assertEqual(self.post(self.a, "Привіт").status_code, 403)
        self.assertEqual(self.post(self.b, "Привіт").status_code, 403)
        self.assertEqual(Message.objects.count(), 0)

    def test_send_requires_post_and_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse("chat:send", args=[self.conv.pk])).status_code, 302)
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse("chat:send", args=[self.conv.pk])).status_code, 405)

    def test_html_in_message_is_returned_as_data_not_markup(self):
        self.post(self.a, "<script>alert(1)</script>")
        data = self.client.get(reverse("chat:messages", args=[self.conv.pk])).json()
        self.assertEqual(data["messages"][0]["text"], "<script>alert(1)</script>")

    def test_detail_page_renders_for_participant(self):
        self.client.force_login(self.a)
        response = self.client.get(reverse("chat:detail", args=[self.conv.pk]))
        self.assertContains(response, 'id="chat"')

    def test_block_and_unblock_buttons_available_in_chat(self):
        """D-05: блокувати співрозмовника можна прямо з чату."""
        self.client.force_login(self.a)
        page = self.client.get(reverse("chat:detail", args=[self.conv.pk]))
        self.assertContains(page, reverse("interactions:block", args=[self.b.pk]))
        self.assertNotContains(page, reverse("interactions:unblock", args=[self.b.pk]))
        self.client.post(reverse("interactions:block", args=[self.b.pk]))
        page = self.client.get(reverse("chat:detail", args=[self.conv.pk]))
        self.assertContains(page, reverse("interactions:unblock", args=[self.b.pk]))
        self.assertNotContains(page, reverse("interactions:block", args=[self.b.pk]))
        # заблокований співрозмовник бачить, що надсилання недоступне, і не може розблокувати за іншого
        self.client.force_login(self.b)
        page = self.client.get(reverse("chat:detail", args=[self.conv.pk]))
        self.assertContains(page, "Надсилання недоступне")
        self.assertEqual(UserBlock.objects.filter(blocker=self.a, blocked=self.b).count(), 1)
