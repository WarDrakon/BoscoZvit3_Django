from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from interactions.models import ContactRequest, is_blocked_between

from . import services
from .forms import RecommendationFilterForm


UK_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UK_ORDER = {ch: i for i, ch in enumerate(UK_ALPHABET)}


def uk_sort_key(text):
    """Ключ сортування за українським алфавітом (у Unicode «і», «ї», «є», «ґ» стоять не на своїх місцях)."""
    return [(0, UK_ORDER[ch]) if ch in UK_ORDER else (1, ord(ch)) for ch in text.casefold()]


def _low_budget(profile, listing):
    """Нижня межа бюджету кандидата: ціна його оголошення або «бюджет від» із параметрів пошуку."""
    if listing:
        return listing.price_per_person
    search = getattr(profile, "search", None)
    if search is None:
        return None
    return search.budget_min if search.budget_min is not None else search.budget_max


# Порядок застосування фільтрів фіксований: так причину порожнього списку можна пояснити точно.
FILTER_ORDER = ("mode", "city", "only_housing", "min_score", "max_budget", "min_age", "max_age")


def _matches(name, value, profile, outcome):
    listing = profile.active_listing
    if name == "mode":
        return profile.search_mode == value
    if name == "city":
        needle = value.casefold()
        return needle in (profile.city or "").casefold() or bool(listing and needle in listing.city.casefold())
    if name == "only_housing":
        return listing is not None
    if name == "min_score":
        return outcome.score is not None and outcome.score >= value
    if name == "max_budget":
        return profile.low_budget is None or profile.low_budget <= value
    if name == "min_age":
        return profile.age is not None and profile.age >= value
    if name == "max_age":
        return profile.age is not None and profile.age <= value
    return True


def apply_filters(results, filters):
    """Застосовує фільтри по черзі. Повертає (список, кроки), де крок = (назва, значення, було, стало)."""
    remaining, steps = list(results), []
    for name in FILTER_ORDER:
        value = filters.get(name)
        if not value:
            continue
        before = len(remaining)
        remaining = [item for item in remaining if _matches(name, value, item[0], item[1])]
        steps.append((name, value, before, len(remaining)))
    return remaining, steps


def _empty_reason(candidates_total, steps, form, hidden_conflicts):
    """Пояснює, чому немає жодного результату (None, якщо пояснювати нічого)."""
    if candidates_total == 0:
        return ("Поки немає інших активних профілів: не враховуються ви, заблоковані користувачі "
                "та ті, хто призупинив пошук.")
    for name, value, before, after in steps:
        if after == 0:
            mode_label = dict(form.fields["mode"].choices).get(value, value)
            return {
                "mode": f"Жоден із {before} кандидатів не має режиму «{mode_label}».",
                "city": f"У місті «{value}» кандидатів не знайдено (до фільтра за містом було {before}).",
                "only_housing": f"Жоден із {before} кандидатів не має активного оголошення про житло.",
                "min_score": f"Жоден із {before} кандидатів не має сумісності від {value}%.",
                "max_budget": f"Мінімальний бюджет усіх {before} кандидатів вищий за {value} грн.",
            }[name]
    if hidden_conflicts:
        return (f"Усі кандидати ({hidden_conflicts}), що відповідають фільтрам, мають критичні конфлікти "
                "з вашими вимогами, тому приховані.")
    return None


@login_required
def recommendations(request):
    form = RecommendationFilterForm(request.GET or None)
    form.is_valid()  # навіть якщо одне поле помилкове, cleaned_data містить усі коректні поля
    filters = dict(getattr(form, "cleaned_data", {}))
    invalid_filters = [str(form.fields[name].label) for name in form.errors] if form.is_bound else []

    results = services.get_recommendations(request.user)
    for profile, _ in results:
        profile.active_listing = next((l for l in profile.user.housing_listings.all() if l.is_active and not l.is_hidden), None)
        profile.low_budget = _low_budget(profile, profile.active_listing)
    visible, steps = apply_filters(results, filters)

    if filters.get("sort") == "budget":
        visible.sort(key=lambda item: (item[0].low_budget is None, item[0].low_budget or 0))
    elif filters.get("sort") == "name":
        visible.sort(key=lambda item: uk_sort_key(item[0].display_name))

    main = [item for item in visible if not item[1].has_critical_conflict]
    conflicted = [item for item in visible if item[1].has_critical_conflict]
    # Стан галочки береться з тих самих очищених даних, що й фільтри: BooleanField не може бути «помилковим»
    show_conflicts = bool(filters.get("show_conflicts"))
    shown_conflicts = conflicted if show_conflicts else []
    hidden_conflicts = 0 if show_conflicts else len(conflicted)
    found_total = len(main) + len(shown_conflicts)

    query = request.GET.copy()
    query.pop("page", None)
    show_query = query.copy()
    show_query["show_conflicts"] = "on"
    page = Paginator(main, 9).get_page(request.GET.get("page"))
    return render(request, "matching/recommendations.html", {
        "form": form, "page": page, "query": query.urlencode(),
        "conflicted": shown_conflicts, "show_conflicts": show_conflicts,
        "hidden_conflicts": hidden_conflicts, "show_conflicts_query": show_query.urlencode(),
        "main_count": len(main), "found_total": found_total,
        "invalid_filters": invalid_filters,
        "empty_reason": _empty_reason(len(results), steps, form, hidden_conflicts) if found_total == 0 else None})


@login_required
def candidate_detail(request, profile_id):
    profile = get_object_or_404(services.profile_queryset(), pk=profile_id, user__is_active=True)
    if profile.user_id == request.user.pk:
        from django.shortcuts import redirect
        return redirect("profiles:view")
    if is_blocked_between(request.user, profile.user):
        return render(request, "404.html", status=404)
    outcome = services.get_match(request.user, profile)
    listings = [l for l in profile.user.housing_listings.all() if l.is_active and not l.is_hidden]
    existing = ContactRequest.objects.filter(
        sender=request.user, receiver=profile.user,
        status__in=[ContactRequest.Status.PENDING, ContactRequest.Status.ACCEPTED]).first()
    incoming = ContactRequest.objects.filter(
        sender=profile.user, receiver=request.user,
        status=ContactRequest.Status.PENDING).first()
    return render(request, "matching/candidate.html", {
        "profile": profile, "lifestyle": getattr(profile, "lifestyle", None), "search": getattr(profile, "search", None),
        "outcome": outcome, "listings": listings, "existing_request": existing, "incoming_request": incoming})
