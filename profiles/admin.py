from django.contrib import admin

from .models import CriterionWeight, LifestylePreference, Profile, SearchPreference


class LifestyleInline(admin.StackedInline):
    model = LifestylePreference
    extra = 0


class SearchInline(admin.StackedInline):
    model = SearchPreference
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "age_display", "user", "city", "search_mode", "is_active_search", "updated_at")
    list_select_related = ("user",)
    list_filter = ("search_mode", "is_active_search", "city")
    search_fields = ("display_name", "user__email", "city")
    inlines = [LifestyleInline, SearchInline]

    @admin.display(description="Вік")
    def age_display(self, obj):
        return obj.age_label


@admin.register(CriterionWeight)
class CriterionWeightAdmin(admin.ModelAdmin):
    list_display = ("profile", "criterion", "weight", "is_critical")
    list_filter = ("criterion", "is_critical")
    search_fields = ("profile__display_name", "profile__user__email")
