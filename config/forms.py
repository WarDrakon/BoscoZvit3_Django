"""Спільні допоміжні класи форм."""
from django import forms

from .person_validators import (NAME_MAX, PersonNameValidator, birth_date_bounds, normalize_name, validate_birth_date)


class StyledFormMixin:
    """Додає CSS-класи до віджетів, щоб усі форми виглядали однаково."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "check"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "select"
            elif isinstance(widget, forms.FileInput):
                css = "file"
            else:
                css = "input"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class LiveValidationMixin:
    """Миттєва перевірка в браузері (static/js/validation.js) + серверна перевірка імен і дати народження.

    Форма оголошує live_names = {"поле": "Мітка"}; поле дати народження (якщо є) підключається автоматично.
    Серверні правила — у config/person_validators.py, JS лише дублює їх для зручності.
    """
    live_names = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, label in self.live_names.items():
            if name in self.fields:
                self.fields[name].widget.attrs.update({"data-validate": "name", "data-label": label, "maxlength": NAME_MAX + 10})
                self.fields[name].error_messages["required"] = f"{label} не може бути порожнім або складатися лише з пробілів."
        if "birth_date" in self.fields:
            low, high = birth_date_bounds()
            self.fields["birth_date"].widget.attrs.update({"data-validate": "birth-date", "min": low.isoformat(), "max": high.isoformat()})

    def _clean_name(self, name):
        value = normalize_name(self.cleaned_data.get(name, ""))
        PersonNameValidator(self.live_names[name])(value)
        return value

    def clean_first_name(self):
        return self._clean_name("first_name")

    def clean_last_name(self):
        return self._clean_name("last_name")

    def clean_display_name(self):
        return self._clean_name("display_name")

    def clean_birth_date(self):
        value = self.cleaned_data.get("birth_date")
        validate_birth_date(value)
        return value
