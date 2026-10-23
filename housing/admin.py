from django.contrib import admin

from .models import HousingListing, HousingPhoto


class PhotoInline(admin.TabularInline):
    model = HousingPhoto
    extra = 0


@admin.register(HousingListing)
class HousingListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "city", "district", "price_per_person", "is_active", "is_hidden", "created_at")
    list_filter = ("is_active", "is_hidden", "city")
    search_fields = ("title", "owner__email", "city", "district")
    inlines = [PhotoInline]
    actions = ["hide_listings", "unhide_listings"]

    @admin.action(description="Приховати оголошення (порушення правил)")
    def hide_listings(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description="Повернути приховані оголошення")
    def unhide_listings(self, request, queryset):
        queryset.update(is_hidden=False)
