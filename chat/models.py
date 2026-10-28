from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.urls import reverse


class ConversationManager(models.Manager):
    def for_user(self, user):
        return self.filter(Q(user_one=user) | Q(user_two=user))

    def get_or_create_between(self, a, b):
        """Пара зберігається впорядковано (менший id — user_one), тож дублікатів розмов немає."""
        first, second = (a, b) if a.pk < b.pk else (b, a)
        conversation, _ = self.get_or_create(user_one=first, user_two=second)
        return conversation


class Conversation(models.Model):
    conversation_id = models.AutoField(primary_key=True)
    user_one = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_first")
    user_two = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations_as_second")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    objects = ConversationManager()

    class Meta:
        verbose_name = "розмова"
        verbose_name_plural = "розмови"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["user_one", "user_two"], name="uniq_conversation_pair"),
            models.CheckConstraint(condition=Q(user_one__lt=F("user_two")), name="conversation_ordered_pair"),
        ]

    def __str__(self):
        return f"Розмова #{self.pk}"

    def get_absolute_url(self):
        return reverse("chat:detail", kwargs={"conversation_id": self.pk})

    def other_user(self, user):
        return self.user_two if self.user_one_id == user.pk else self.user_one

    def has_participant(self, user):
        return user.pk in (self.user_one_id, self.user_two_id)


class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "повідомлення"
        verbose_name_plural = "повідомлення"
        ordering = ["message_id"]
        indexes = [models.Index(fields=["conversation", "message_id"]), models.Index(fields=["read_at"])]

    def __str__(self):
        return f"#{self.message_id} від {self.sender_id}"
