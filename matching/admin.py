from django.contrib import admin

from .models import MatchResult


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display = ("user", "candidate", "score", "has_critical_conflict", "data_coverage", "calculated_at")
    list_filter = ("has_critical_conflict",)
    readonly_fields = ("details",)
