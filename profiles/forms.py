from django import forms

from config.forms import StyledFormMixin

from .models import CRITERIA, CriterionWeight, LifestylePreference, Profile, SearchPreference

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
ANY = "Неважливо"
UNSPECIFIED = "Не вказано"


class ProfileForm(StyledFormMixin, forms.ModelForm):
    move_in_date = forms.DateField(label="Орієнтовна дата заселення", required=False, widget=DATE_WIDGET)

    class Meta:
        model = Profile
        fields = ["display_name", "photo", "city", "occupation", "about", "search_mode", "move_in_date", "is_active_search"]
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
    req_min_cleanliness = forms.TypedChoiceField(
        label="Мінімально прийнятна охайність співмешканця", required=False, coerce=int, empty_value=None,
        choices=[("", ANY)] + [(i, f"Не нижче {i}") for i in range(1, 6)])
    req_max_noise = forms.TypedChoiceField(
        label="Максимально прийнятний шум", required=False, coerce=int, empty_value=None,
        choices=[("", ANY)] + [(i, f"Не вище {i}") for i in range(1, 6)])

    class Meta:
        model = SearchPreference
        fields = ["city", "district", "budget_min", "budget_max", "move_in_date", "req_sleep", "req_min_cleanliness",
                  "req_max_noise", "req_guests", "req_smoking", "req_pets", "req_chores"]
        widgets = {"budget_min": forms.NumberInput(attrs={"min": 0, "step": 100, "placeholder": "напр. 5000"}),
                   "budget_max": forms.NumberInput(attrs={"min": 0, "step": 100, "placeholder": "напр. 8000"})}

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        saved = {w.criterion: w for w in profile.weights.all()} if profile else {}
        for key, label in CRITERIA:
            current = saved.get(key)
            self.fields[f"w_{key}"] = forms.TypedChoiceField(
                label=f"Важливість: {label}", coerce=int, initial=current.weight if current else 3,
                choices=[(i, str(i)) for i in range(1, 6)], widget=forms.Select(attrs={"class": "select"}))
            self.fields[f"c_{key}"] = forms.BooleanField(
                label=f"Критична вимога: {label}", required=False, initial=current.is_critical if current else False,
                widget=forms.CheckboxInput(attrs={"class": "check"}))

    def weight_rows(self):
        """Рядки таблиці важливості для шаблону."""
        return [{"label": label, "weight": self[f"w_{key}"], "critical": self[f"c_{key}"]} for key, label in CRITERIA]

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            for key, _ in CRITERIA:
                CriterionWeight.objects.update_or_create(
                    profile=self.profile, criterion=key,
                    defaults={"weight": self.cleaned_data[f"w_{key}"], "is_critical": self.cleaned_data[f"c_{key}"]})
        return instance
