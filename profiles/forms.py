from django import forms

from housing.models import HousingListing

from config.forms import LiveValidationMixin, StyledFormMixin

from .models import CRITERIA, CriterionWeight, LifestylePreference, Profile, SearchPreference

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
ANY = "Неважливо"
UNSPECIFIED = "Не вказано"


class ProfileForm(LiveValidationMixin, StyledFormMixin, forms.ModelForm):
    live_names = {"display_name": "Публічне ім’я"}

    birth_date = forms.DateField(label="Дата народження", required=False, widget=DATE_WIDGET,
                                 help_text="Вік має бути від 18 до 100 років. Він обчислюється автоматично; іншим показується лише вік.")
    move_in_date = forms.DateField(label="Орієнтовна дата заселення", required=False, widget=DATE_WIDGET)

    class Meta:
        model = Profile
        fields = ["display_name", "photo", "city", "occupation", "about", "search_mode", "birth_date", "move_in_date", "is_active_search"]
        widgets = {"about": forms.Textarea(attrs={"rows": 4, "placeholder": "Розкажіть про свій розпорядок, інтереси та очікування від спільного проживання"})}
        help_texts = {"photo": "JPG, PNG або WEBP, до 5 МБ.",
                      "is_active_search": "Вимкніть, щоб тимчасово не показуватись в рекомендаціях."}


def _with_blank(field, label):
    field.choices = [("", label)] + [c for c in field.choices if c[0] != ""]


class LifestyleForm(StyledFormMixin, forms.ModelForm):
    cleanliness = forms.TypedChoiceField(label="Рівень охайності", required=False, coerce=int, empty_value=None,
                                         choices=[("", UNSPECIFIED), (1, "1 — невимогливий"), (2, "2"), (3, "3 — звичайний"),
                                                  (4, "4"), (5, "5 — дуже охайний")])
    noise_level = forms.TypedChoiceField(label="Звичний рівень шуму", required=False, coerce=int, empty_value=None,
                                         choices=[("", UNSPECIFIED), (1, "1 — майже тиша"), (2, "2"), (3, "3 — помірний"),
                                                  (4, "4"), (5, "5 — гучно")])

    class Meta:
        model = LifestylePreference
        fields = ["sleep_schedule", "cleanliness", "noise_level", "guests_frequency", "smoking", "pets",
                  "work_schedule", "chores_attitude"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["sleep_schedule", "guests_frequency", "smoking", "pets", "work_schedule", "chores_attitude"]:
            _with_blank(self.fields[name], UNSPECIFIED)


class SearchForm(StyledFormMixin, forms.ModelForm):
    """Параметри пошуку + важливість критеріїв (поля w_<критерій>, c_<критерій>)."""

    move_in_date = forms.DateField(label="Бажана дата заселення", required=False, widget=DATE_WIDGET)
    req_age_min = forms.IntegerField(label="Вік від", required=False, min_value=18, max_value=120,
                                     widget=forms.NumberInput(attrs={"placeholder": "напр. 18"}))
    req_age_max = forms.IntegerField(label="Вік до", required=False, min_value=18, max_value=120,
                                     widget=forms.NumberInput(attrs={"placeholder": "напр. 35"}))
    req_min_cleanliness = forms.TypedChoiceField(
        label="Мінімально прийнятна охайність співмешканця", required=False, coerce=int, empty_value=None,
        choices=[("", ANY)] + [(i, f"Не нижче {i}") for i in range(1, 6)])
    req_max_noise = forms.TypedChoiceField(
        label="Максимально прийнятний шум", required=False, coerce=int, empty_value=None,
        choices=[("", ANY)] + [(i, f"Не вище {i}") for i in range(1, 6)])

    class Meta:
        model = SearchPreference
        fields = ["city", "district", "budget_min", "budget_max", "move_in_date", "req_age_min", "req_age_max",
                  "req_sleep", "req_min_cleanliness", "req_max_noise", "req_guests", "req_smoking", "req_pets", "req_chores"]
        widgets = {"city": forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Оберіть або введіть місто"}),
                   "district": forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Оберіть або введіть район"}),
                   "budget_min": forms.NumberInput(attrs={"min": 0, "step": 100, "placeholder": "напр. 5000"}),
                   "budget_max": forms.NumberInput(attrs={"min": 0, "step": 100, "placeholder": "напр. 8000"})}

    # Визначаємо, чи користувач справді задав вимогу для критерію.
    CRITERION_FIELDS = {
        "budget": ("budget_min", "budget_max"),
        "location": ("city", "district"),
        "move_in": ("move_in_date",),
        "age": ("req_age_min", "req_age_max"),
        "sleep": ("req_sleep",),
        "cleanliness": ("req_min_cleanliness",),
        "noise": ("req_max_noise",),
        "guests": ("req_guests",),
        "smoking": ("req_smoking",),
        "pets": ("req_pets",),
        "chores": ("req_chores",),
    }

    @staticmethod
    def _specified(value):
        return value is not None and value != "" and value != "any"

    def _active(self, key, values):
        return any(self._specified(values.get(field)) for field in self.CRITERION_FIELDS[key])

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        # Only public housing locations are offered as suggestions; free text stays valid.
        locations = HousingListing.objects.filter(is_active=True, is_hidden=False).values_list("city", "district").distinct()
        self.city_suggestions = sorted({city.strip() for city, _ in locations if city and city.strip()})
        self.district_suggestions = {}
        for city, district in locations:
            if city and city.strip() and district and district.strip():
                self.district_suggestions.setdefault(city.strip(), set()).add(district.strip())
        self.district_suggestions = {city: sorted(districts) for city, districts in self.district_suggestions.items()}
        saved = {w.criterion: w for w in profile.weights.all()} if profile else {}
        for key, label in CRITERIA:
            current = saved.get(key)
            self.fields[f"w_{key}"] = forms.TypedChoiceField(
                label=f"Наскільки важливо: {label}", required=False, coerce=int, empty_value=3, initial=current.weight if current else 3,
                choices=[(i, str(i)) for i in range(1, 6)], widget=forms.Select(attrs={"class": "select"}))
            self.fields[f"c_{key}"] = forms.BooleanField(
                label=f"Обов’язкова умова: {label}", required=False, initial=current.is_critical if current else False,
                widget=forms.CheckboxInput(attrs={"class": "check"}))

    def clean(self):
        cleaned = super().clean()
        for key, _ in CRITERIA:
            if not self._active(key, cleaned):
                cleaned[f"w_{key}"] = 3
                cleaned[f"c_{key}"] = False
        return cleaned

    def weight_rows(self):
        """Рядки таблиці важливості для шаблону."""
        return [{"key": key, "label": label, "weight": self[f"w_{key}"], "critical": self[f"c_{key}"]} for key, label in CRITERIA if key != "age"]

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            for key, _ in CRITERIA:
                CriterionWeight.objects.update_or_create(
                    profile=self.profile, criterion=key,
                    defaults={"weight": self.cleaned_data[f"w_{key}"], "is_critical": self.cleaned_data[f"c_{key}"]})
        return instance
