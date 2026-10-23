from django.conf import settings
from django.db import models


class MatchResult(models.Model):
    """Збережений результат розрахунку сумісності (кеш + історія для пояснень)."""

    match_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="match_results")
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matched_as_candidate")
    score = models.DecimalField("Сумісність, %", max_digits=5, decimal_places=1, null=True, blank=True)
    score_user_to_candidate = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    score_candidate_to_user = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    data_coverage = models.PositiveSmallIntegerField("Повнота даних, %", null=True, blank=True)
    has_critical_conflict = models.BooleanField(default=False)
    details = models.JSONField(default=dict)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "результат підбору"
        verbose_name_plural = "результати підбору"
        constraints = [models.UniqueConstraint(fields=["user", "candidate"], name="uniq_match_pair")]
        indexes = [models.Index(fields=["user", "-score"])]

    def __str__(self):
        return f"{self.user} ↔ {self.candidate}: {self.score}"
