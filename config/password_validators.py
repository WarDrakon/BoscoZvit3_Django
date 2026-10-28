"""Додаткові валідатори пароля для реєстрації (повідомлення українською).

Правила мають збігатися з перевіркою в браузері (static/js/password.js): великі/малі літери та цифри — за
категоріями Unicode, спеціальний символ — будь-який знак, що не є літерою, цифрою чи пробілом.
"""
import re

from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890", "йцукенгшщзхї", "фівапролджє", "ячсмитьбю")


def char_classes(password):
    """Які види символів є в паролі: {lower, upper, digit, special}."""
    return {
        "lower": any(c.islower() for c in password),
        "upper": any(c.isupper() for c in password),
        "digit": any(c.isdecimal() for c in password),
        "special": any(not c.isalnum() and not c.isspace() for c in password),
    }


class PasswordComplexityValidator:
    """Вимагає малу й велику літери, цифру та спеціальний символ."""

    messages = {
        "lower": "Додайте хоча б одну малу літеру.",
        "upper": "Додайте хоча б одну велику літеру.",
        "digit": "Додайте хоча б одну цифру.",
        "special": "Додайте хоча б один спеціальний символ (наприклад, ! ? # $ % -).",
    }

    def validate(self, password, user=None):
        classes = char_classes(password)
        errors = [ValidationError(text, code=f"password_no_{key}") for key, text in self.messages.items() if not classes[key]]
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return "Пароль має містити великі й малі літери, цифри та спеціальні символи."


class ObviousPasswordValidator:
    """Забороняє очевидні варіації поширених паролів: «Password1!», «P@ssw0rd», «Qwerty123», «Aa1!Aa1!»."""

    code = "password_obvious"
    message = "Пароль надто очевидний або поширений: його легко підібрати. Придумайте менш передбачуваний."

    def __init__(self):
        self.common = CommonPasswordValidator().passwords

    def _is_obvious(self, password):
        low = password.lower()
        for form in {low, low.translate(LEET)}:
            core = re.sub(r"^[\W\d_]+|[\W\d_]+$", "", form)  # «123Password!» → «password»
            if form in self.common or (len(core) >= 5 and core in self.common):
                return True
            letters = re.sub(r"[\W\d_]+", "", form)
            if len(letters) >= 5 and any(letters in row or letters in row[::-1] for row in KEYBOARD_ROWS):
                return True
        return any(len(password) >= 2 * n and len(password) % n == 0 and password == password[:n] * (len(password) // n)
                   for n in range(1, 5))

    def validate(self, password, user=None):
        if self._is_obvious(password):
            raise ValidationError(self.message, code=self.code)

    def get_help_text(self):
        return "Не використовуйте очевидні й поширені паролі та їхні варіації."


def registration_validators():
    """Валідатори з settings.AUTH_PASSWORD_VALIDATORS плюс складність та перевірка на очевидність."""
    from django.contrib.auth import password_validation
    return password_validation.get_default_password_validators() + [PasswordComplexityValidator(), ObviousPasswordValidator()]
