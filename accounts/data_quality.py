"""Пошук некоректних імен і дат народження в наявних записах (для адмінпанелі та команди fix_user_data)."""
from config.person_validators import birth_date_problem, name_problem


def user_issues(user):
    """Список {"field", "value", "problem"} для користувача та його профілю. Порожній — дані коректні."""
    issues = []
    for field, label in (("first_name", "Ім’я"), ("last_name", "Прізвище")):
        problem = name_problem(getattr(user, field), label)
        if problem:
            issues.append({"field": field, "value": getattr(user, field), "problem": problem})
    profile = getattr(user, "profile", None)
    if profile is not None:
        problem = name_problem(profile.display_name, "Публічне ім’я")
        if problem:
            issues.append({"field": "profile.display_name", "value": profile.display_name, "problem": problem})
        problem = birth_date_problem(profile.birth_date)
        if problem:
            issues.append({"field": "profile.birth_date", "value": profile.birth_date, "problem": problem})
    return issues
