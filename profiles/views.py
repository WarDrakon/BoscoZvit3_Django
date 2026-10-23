from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from housing.models import HousingListing
from interactions.models import ContactRequest

from .forms import LifestyleForm, ProfileForm, SearchForm
from .models import LifestylePreference, SearchPreference


def _lifestyle(profile):
    return LifestylePreference.objects.get_or_create(profile=profile)[0]


def _search(profile):
    return SearchPreference.objects.get_or_create(profile=profile, defaults={"city": profile.city})[0]


def profile_completeness(profile):
    """Чек-лист заповнення: допомагає користувачу зрозуміти, що ще потрібно для точних рекомендацій."""
    lifestyle, search = _lifestyle(profile), _search(profile)
    habit_fields = ["sleep_schedule", "cleanliness", "noise_level", "guests_frequency", "smoking", "pets", "chores_attitude"]
    filled = sum(1 for f in habit_fields if getattr(lifestyle, f) not in ("", None))
    steps = [
        {"title": "Профіль", "done": bool(profile.city and profile.about),
         "hint": "Вкажіть місто та кілька слів про себе.", "url": "profiles:edit"},
        {"title": "Анкета звичок", "done": filled >= 5, "hint": f"Заповнено {filled} із {len(habit_fields)} полів.",
         "url": "profiles:lifestyle"},
        {"title": "Параметри пошуку", "done": bool(search.city and (search.budget_min or search.budget_max)),
         "hint": "Вкажіть місто та бюджет.", "url": "profiles:search"},
    ]
    percent = round(100 * sum(s["done"] for s in steps) / len(steps))
    return steps, percent


@login_required
def dashboard(request):
    profile = request.user.profile
    steps, percent = profile_completeness(profile)
    context = {
        "profile": profile, "steps": steps, "percent": percent,
        "pending_requests": ContactRequest.objects.filter(receiver=request.user, status=ContactRequest.Status.PENDING).count(),
        "my_listings": HousingListing.objects.filter(owner=request.user).count(),
    }
    return render(request, "profiles/dashboard.html", context)


@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, "profiles/profile.html", {
        "profile": profile, "lifestyle": _lifestyle(profile), "search": _search(profile)})


@login_required
def profile_edit(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Профіль збережено.")
        return redirect("profiles:view")
    return render(request, "profiles/profile_form.html", {"form": form, "title": "Редагування профілю"})


@login_required
def lifestyle_edit(request):
    form = LifestyleForm(request.POST or None, instance=_lifestyle(request.user.profile))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Анкету збережено. Рекомендації оновлено.")
        return redirect("profiles:view")
    return render(request, "profiles/profile_form.html", {
        "form": form, "title": "Анкета побутових звичок",
        "intro": "Опишіть, як ви живете насправді. Це ваші факти — вимоги до співмешканця вказуються окремо в параметрах пошуку. Поля можна пропустити, але тоді сумісність оцінюватиметься менш точно."})


@login_required
def search_edit(request):
    profile = request.user.profile
    form = SearchForm(request.POST or None, instance=_search(profile), profile=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Параметри пошуку збережено.")
        return redirect("matching:recommendations")
    return render(request, "profiles/search_form.html", {"form": form})
