"""Перевірка імені, прізвища та дати народження. Повідомлення українською.

Правила дзеркально повторює static/js/validation.js (миттєва перевірка в браузері); остаточною є ця, серверна.
"""
import unicodedata
from datetime import date

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

NAME_MIN, NAME_MAX = 2, 50
AGE_MIN, AGE_MAX = 18, 100
NAME_EXTRA_CHARS = " -'’ʼ"  # пробіл, дефіс і апострофи: «Анна-Марія», «Д’Артаньян», «Марія Луїза»


def normalize_name(value):
    """Обрізає пробіли по краях і замінює повторні пробіли одним."""
    return " ".join((value or "").split())


def _is_letter(char):
    return unicodedata.category(char).startswith("L")


def _is_mark(char):
    return unicodedata.category(char).startswith("M")


@deconstructible
class PersonNameValidator:
    """Ім’я/прізвище/публічне ім’я: 2–50 символів, лише літери, пробіли, дефіс і апостроф, щонайменше дві літери."""

    def __init__(self, label="Ім’я"):
        self.label = label

    def __call__(self, value):
        name = normalize_name(value)
        label = self.label
        if not name:
            raise ValidationError(f"{label} не може бути порожнім або складатися лише з пробілів.", code="name_blank")
        if name.replace(" ", "").isdecimal():
            raise ValidationError(f"{label} не може складатися лише з цифр.", code="name_digits")
        if len(name) < NAME_MIN:
            raise ValidationError(f"{label} має містити щонайменше {NAME_MIN} символи.", code="name_short")
        if len(name) > NAME_MAX:
            raise ValidationError(f"{label} не може бути довшим за {NAME_MAX} символів.", code="name_long")
        if any(not (_is_letter(c) or _is_mark(c) or c in NAME_EXTRA_CHARS) for c in name):
            raise ValidationError(f"{label} може містити лише літери, пробіли, дефіс і апостроф (без цифр і спецсимволів).", code="name_chars")
        if sum(_is_letter(c) for c in name) < 2:
            raise ValidationError(f"{label} має містити щонайменше дві літери.", code="name_letters")
        if not _is_letter(name[0]) or not (_is_letter(name[-1]) or _is_mark(name[-1])):
            raise ValidationError(f"{label} має починатися й закінчуватися літерою.", code="name_edges")

    def __eq__(self, other):
        return isinstance(other, PersonNameValidator) and self.label == other.label


def calculate_age(birth_date, today=None):
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def validate_birth_date(value, today=None):
    """Не в майбутньому, вік від 18 до 100 років."""
    if value is None:
        return
    today = today or date.today()
    if value > today:
        raise ValidationError("Дата народження не може бути в майбутньому.", code="birth_future")
    age = calculate_age(value, today)
    if age < AGE_MIN:
        raise ValidationError(f"Сервіс доступний лише повнолітнім: вік має бути від {AGE_MIN} років.", code="birth_underage")
    if age > AGE_MAX:
        raise ValidationError(f"Вік не може перевищувати {AGE_MAX} років. Перевірте дату народження.", code="birth_too_old")


first_name_validator = PersonNameValidator("Ім’я")
last_name_validator = PersonNameValidator("Прізвище")
display_name_validator = PersonNameValidator("Публічне ім’я")


def name_problem(value, label="Ім’я"):
    """Текст помилки або None — для звітів і адмінпанелі."""
    try:
        PersonNameValidator(label)(value)
    except ValidationError as error:
        return error.messages[0]
    return None


def birth_date_problem(value):
    try:
        validate_birth_date(value)
    except ValidationError as error:
        return error.messages[0]
    return None


def _years_ago(day, years):
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 лютого → 28 лютого
        return day.replace(year=day.year - years, day=28)


def birth_date_bounds(today=None):
    """(найраніша, найпізніша) допустимі дати народження — для атрибутів min/max поля дати."""
    from datetime import timedelta
    today = today or date.today()
    return _years_ago(today, AGE_MAX + 1) + timedelta(days=1), _years_ago(today, AGE_MIN)
