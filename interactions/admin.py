from django.contrib import admin

from .models import ContactRequest, Report, UserBlock


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("sender__email", "receiver__email")


@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("report_id", "reason", "reporter", "reported_user", "housing", "status", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("reporter__email", "reported_user__email", "description")
    actions = ["mark_resolved", "mark_rejected", "hide_reported_listings", "deactivate_reported_users"]

    @admin.action(description="Позначити як розглянуті")
    def mark_resolved(self, request, queryset):
        queryset.update(status=Report.Status.RESOLVED)

    @admin.action(description="Відхилити скарги")
    def mark_rejected(self, request, queryset):
        queryset.update(status=Report.Status.REJECTED)

    @admin.action(description="Приховати оголошення, на які скаржаться")
    def hide_reported_listings(self, request, queryset):
        for report in queryset.select_related("housing"):
            if report.housing:
                report.housing.is_hidden = True
                report.housing.save(update_fields=["is_hidden"])
        queryset.update(status=Report.Status.RESOLVED)

    @admin.action(description="Деактивувати акаунти, на які скаржаться")
    def deactivate_reported_users(self, request, queryset):
        for report in queryset.select_related("reported_user"):
            user = report.reported_user
            if user and not user.is_staff:
                user.is_active = False
                user.save(update_fields=["is_active"])
        queryset.update(status=Report.Status.RESOLVED)
