from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ContactRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Очікує відповіді"
        ACCEPTED = "accepted", "Прийнято"
        DECLINED = "declined", "Відхилено"
        CANCELLED = "cancelled", "Скасовано"

    request_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_requests")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_requests")
    housing = models.ForeignKey("housing.HousingListing", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="contact_requests")
    message = models.CharField("Повідомлення", max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "запит на контакт"
        verbose_name_plural = "запити на контакт"
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=~Q(sender=F("receiver")), name="request_not_to_self")]
        indexes = [models.Index(fields=["receiver", "status"])]

    def __str__(self):
        return f"{self.sender} → {self.receiver} ({self.status})"


class UserBlock(models.Model):
    block_id = models.AutoField(primary_key=True)
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "блокування"
        verbose_name_plural = "блокування"
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="uniq_block_pair"),
            models.CheckConstraint(condition=~Q(blocker=F("blocked")), name="block_not_self"),
        ]

    def __str__(self):
        return f"{self.blocker} заблокував {self.blocked}"


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Спам або реклама"
        FRAUD = "fraud", "Шахрайство"
        ABUSE = "abuse", "Образи або погрози"
        FAKE = "fake", "Недостовірні дані"
        OTHER = "other", "Інше"

    class Status(models.TextChoices):
        NEW = "new", "Нова"
        RESOLVED = "resolved", "Розглянуто"
        REJECTED = "rejected", "Відхилено"

    report_id = models.AutoField(primary_key=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                                      related_name="reports_received")
    housing = models.ForeignKey("housing.HousingListing", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="reports")
    reason = models.CharField("Причина", max_length=10, choices=Reason.choices)
    description = models.TextField("Опис", max_length=1000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "скарга"
        verbose_name_plural = "скарги"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Скарга #{self.report_id}: {self.get_reason_display()}"


def is_blocked_between(user_a, user_b):
    """True, якщо будь-хто з двох заблокував іншого."""
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)).exists()


def blocked_user_ids(user):
    """ID усіх, з ким у користувача є блокування в будь-який бік."""
    pairs = UserBlock.objects.filter(Q(blocker=user) | Q(blocked=user)).values_list("blocker_id", "blocked_id")
    return {uid for pair in pairs for uid in pair} - {user.pk}
