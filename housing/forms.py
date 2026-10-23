from django import forms
from django.conf import settings

from config.forms import StyledFormMixin
from config.validators import validate_image_file

from .models import HousingListing


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)] if data else []


class ListingForm(StyledFormMixin, forms.ModelForm):
    photos = MultipleImageField(label="Фотографії", required=False,
                                widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
                                help_text="До 8 фото, JPG/PNG/WEBP, кожне до 5 МБ.")

    class Meta:
        model = HousingListing
        fields = ["title", "city", "district", "address", "price_per_person", "rooms", "free_places", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6}), "price_per_person": forms.NumberInput(attrs={"min": 1, "step": 100})}
        help_texts = {"address": "Бачите лише ви та користувачі, чий запит ви прийняли."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photos"].widget.attrs["class"] = "file"

    def clean_photos(self):
        photos = self.cleaned_data.get("photos") or []
        for photo in photos:
            validate_image_file(photo)
        existing = self.instance.photos.count() if self.instance.pk else 0
        if existing + len(photos) > settings.MAX_LISTING_PHOTOS:
            raise forms.ValidationError(f"Можна додати не більше {settings.MAX_LISTING_PHOTOS} фотографій до одного оголошення.")
        return photos


class ListingFilterForm(StyledFormMixin, forms.Form):
    city = forms.CharField(label="Місто", required=False)
    district = forms.CharField(label="Район", required=False)
    max_price = forms.IntegerField(label="Ціна до, грн", required=False, min_value=1)
    sort = forms.ChoiceField(label="Сортування", required=False,
                             choices=[("new", "Спочатку нові"), ("cheap", "Спочатку дешевші"), ("expensive", "Спочатку дорожчі")])
