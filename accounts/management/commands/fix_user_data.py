"""Безпечне виправлення наявних некоректних імен і дат народження. Користувачів НЕ видаляє.

За замовчуванням — лише звіт (нічого не змінює). З --apply:
  • зайві пробіли в іменах прибираються (дані не втрачаються);
  • некоректна дата народження (майбутня, до 18 чи понад 100 років) очищається → у кабінеті «Вік не вказано»,
    вік не вигадується; користувач заповнить дату сам. Стару дату видно у виводі;
  • некоректне публічне ім’я замінюється на ім’я з акаунта, якщо воно коректне;
  • некоректні ім’я/прізвище в акаунті лише позначаються: їх неможливо вгадати, користувач виправить їх у налаштуваннях
    (форми не збережуть дані, поки поле не буде коректним), а адміністратор бачить позначку в адмінпанелі.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.data_quality import user_issues
from config.person_validators import birth_date_problem, name_problem, normalize_name

User = get_user_model()


class Command(BaseCommand):
    help = "Знаходить і (з --apply) безпечно виправляє некоректні імена та дати народження. Нічого не видаляє."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Застосувати виправлення (без цього прапорця — лише звіт).")

    def handle(self, *args, apply=False, **options):
        fixed = flagged = checked = 0
        for user in User.objects.select_related("profile").order_by("pk").iterator():
            checked += 1
            changes = []
            profile = getattr(user, "profile", None)

            # 1. Нормалізація пробілів — безпечна, нічого не втрачає
            for obj, field in [(user, "first_name"), (user, "last_name"), (profile, "display_name")]:
                if obj is None:
                    continue
                old = getattr(obj, field)
                new = normalize_name(old)
                if new != old and (not name_problem(new) or name_problem(old)):
                    setattr(obj, field, new)
                    changes.append(f"{field}: {old!r} → {new!r} (прибрано зайві пробіли)")

            # 2. Некоректна дата народження → «Вік не вказано»
            if profile is not None and birth_date_problem(profile.birth_date):
                changes.append(f"birth_date: {profile.birth_date} → порожньо (некоректна дата, вік не вказано)")
                profile.birth_date = None

            # 3. Некоректне публічне ім’я → ім’я з акаунта, якщо воно коректне
            if profile is not None and name_problem(profile.display_name, "Публічне ім’я") and not name_problem(user.first_name):
                changes.append(f"display_name: {profile.display_name!r} → {user.first_name!r} (ім’я з акаунта)")
                profile.display_name = user.first_name

            if changes and apply:
                user.save(update_fields=["first_name", "last_name"])
                if profile is not None:
                    profile.save(update_fields=["display_name", "birth_date"])
                fixed += 1
            elif changes:
                fixed += 1
            for line in changes:
                self.stdout.write(f"[{user.pk}] {user.email}: {line}")

            for issue in user_issues(user):  # що лишилося після (можливих) виправлень — потребує ручної правки
                flagged += 1
                self.stdout.write(self.style.WARNING(
                    f"[{user.pk}] {user.email}: потребує ручного виправлення — {issue['field']} = {issue['value']!r}: {issue['problem']}"))

        mode = "Виправлено" if apply else "Буде виправлено з --apply (зараз нічого не змінено)"
        self.stdout.write(self.style.SUCCESS(f"Перевірено користувачів: {checked}. {mode}: {fixed}. Лишиться для ручного виправлення: {flagged}."))

