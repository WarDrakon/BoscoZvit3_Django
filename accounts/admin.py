from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm

from .data_quality import user_issues
from .models import User


class AdminAddUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "first_name", "last_name", "age_display", "data_check", "is_active", "is_staff", "date_joined")
    list_select_related = ("profile",)
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-date_joined",)
    add_form = AdminAddUserForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Особисті дані", {"fields": ("first_name", "last_name")}),
        ("Права доступу", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Дати", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "password1", "password2")}),
    )
    actions = ["deactivate_users", "activate_users"]

    @admin.display(description="Вік")
    def age_display(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.age_label if profile else "Вік не вказано"

    @admin.display(description="Перевірка даних")
    def data_check(self, obj):
        issues = user_issues(obj)
        return "Потрібне виправлення: " + "; ".join(i["problem"] for i in issues) if issues else "✓"

    @admin.action(description="Деактивувати вибраних користувачів")
    def deactivate_users(self, request, queryset):
        queryset.exclude(pk=request.user.pk).update(is_active=False)

    @admin.action(description="Активувати вибраних користувачів")
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
