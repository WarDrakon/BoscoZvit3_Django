"""Алгоритм підтримки прийняття рішень для підбору співмешканців.

Без машинного навчання й випадкових значень. Результат повністю відтворюваний.

Схема розрахунку для пари (A, B):
1. Для кожного критерію рахуємо оцінку відповідності s ∈ [0; 1] у двох напрямках:
   «вимоги A ↔ звички/умови B» та «вимоги B ↔ звички/умови A».
   Якщо користувач обрав «Неважливо», критерій у цьому напрямку не враховується.

2. Напрямкова оцінка: S = Σ(wᵢ·sᵢ) / Σwᵢ, де wᵢ — вага критерію, задана тим, чиї вимоги перевіряються.
3. Критичні вимоги (is_critical) перевіряються окремо: якщо sᵢ < 0.5 — кандидат має критичний конфлікт.
   Різні міста пошуку — завжди критичний конфлікт.
4. Взаємна сумісність: M = 0.6·середнє(S_AB, S_BA) + 0.4·min(S_AB, S_BA).
   Мінімум штрафує односторонню відповідність: добре для A, але неприйнятно для B — не взаємний збіг.
"""
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Prefetch

from housing.models import HousingListing
from interactions.models import blocked_user_ids

from .models import MatchResult

DEFAULT_WEIGHT = 3
CONFLICT_THRESHOLD = 0.5   # нижче — вимога фактично не виконується
CONCERN_THRESHOLD = 0.6    # нижче — потенційна проблема
STRENGTH_THRESHOLD = 0.8   # від — сильна сторона
MEAN_SHARE, MIN_SHARE = 0.6, 0.4
PRELIMINARY_COVERAGE = 60  # якщо охоплено менше % критеріїв — оцінка «попередня»

NEUTRAL_SCORE = 0.5        # оцінка критерію, для якого бракує даних
NOT_REQUIRED = "not_required"  # користувач обрав «Неважливо»

LABELS = {
    "budget": "Бюджет", "location": "Місто та район", "move_in": "Дата заселення", "sleep": "Режим сну",
    "cleanliness": "Чистота", "noise": "Рівень шуму", "guests": "Гості", "smoking": "Куріння",
    "pets": "Домашні тварини", "chores": "Побутові обов’язки",
}
GOOD_TEXT = {
    "budget": "Бюджети збігаються", "location": "Збігається місто та район", "move_in": "Близькі дати заселення",
    "sleep": "Схожий режим сну", "cleanliness": "Рівень чистоти відповідає очікуванням",
    "noise": "Рівень шуму відповідає очікуванням", "guests": "Схоже ставлення до гостей",
    "smoking": "Ставлення до куріння збігається", "pets": "Немає суперечностей щодо тварин",
    "chores": "Схоже ставлення до побутових обов’язків",
}
BAD_TEXT = {
    "budget": "Бюджети суттєво відрізняються", "location": "Різні місто або район", "move_in": "Значна різниця в датах заселення",
    "sleep": "Різний режим сну", "cleanliness": "Рівень чистоти нижчий за очікуваний",
    "noise": "Рівень шуму може не влаштувати", "guests": "Різне ставлення до гостей",
    "smoking": "Конфлікт щодо куріння", "pets": "Конфлікт щодо домашніх тварин",
    "chores": "Різне ставлення до побутових обов’язків",
}
SIDE_TEXT = {"you": "за вашими вимогами", "candidate": "за вимогами кандидата", "both": "для обох сторін"}

ORDER_SLEEP = {"early": 0, "regular": 1, "late": 2}
ORDER_GUESTS = {"never": 0, "rare": 1, "sometimes": 2, "often": 3}
ORDER_CHORES = {"split": 0, "flexible": 1, "minimal": 2}


@dataclass
class Snapshot:
    """Усі дані користувача, потрібні для порівняння. Відокремлює алгоритм від ORM, що спрощує тестування."""
    user_id: int
    name: str = ""
    city: str = ""
    district: str = ""
    budget_min: int | None = None
    budget_max: int | None = None
    move_in: date | None = None
    habits: dict = field(default_factory=dict)
    reqs: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)
    critical: set = field(default_factory=set)
    listing: dict | None = None  # {"city","district","price"} для активного оголошення

    def weight(self, criterion):
        return self.weights.get(criterion, DEFAULT_WEIGHT)


# ---------------------------------------------------------------- оцінки окремих критеріїв

def _norm(value):
    return (value or "").strip().casefold()


def _budget_range(s):
    if s.listing:  # власник житла пропонує фіксовану ціну
        return s.listing["price"], s.listing["price"]
    low, high = s.budget_min, s.budget_max
    if low is None and high is None:
        return None
    low = low or 0
    high = high if high is not None else low
    return low, max(high, low)


def _score_budget(seeker, target):
    a, b = _budget_range(seeker), _budget_range(target)
    if a is None or b is None:
        return None
    overlap = min(a[1], b[1]) - max(a[0], b[0])
    if overlap >= 0:
        width = min(a[1] - a[0], b[1] - b[0])
        return 1.0 if width <= 0 else 0.7 + 0.3 * min(1.0, overlap / width)
    reference = max(min(a[1], b[1]), 1)
    return max(0.0, 0.6 * (1 - (-overlap) / (0.3 * reference)))


def _location(s):
    if s.listing:
        return s.listing["city"], s.listing["district"]
    return s.city, s.district


def _score_location(seeker, target):
    (city_a, district_a), (city_b, district_b) = _location(seeker), _location(target)
    if not _norm(city_a) or not _norm(city_b):
        return None
    if _norm(city_a) != _norm(city_b):
        return 0.0
    if not _norm(district_a):
        return 1.0  # район не важливий
    if not _norm(district_b):
        return 0.7
    return 1.0 if _norm(district_a) == _norm(district_b) else 0.4


def _score_move_in(seeker, target):
    if not seeker.move_in or not target.move_in:
        return None
    days = abs((seeker.move_in - target.move_in).days)
    for limit, score in ((14, 1.0), (30, 0.8), (60, 0.5), (90, 0.25)):
        if days <= limit:
            return score
    return 0.0


def _score_sleep(seeker, target):
    wanted, actual = seeker.reqs.get("sleep", "any"), target.habits.get("sleep")
    if wanted in ("any", "", None):
        return NOT_REQUIRED
    if actual not in ORDER_SLEEP:
        return None
    return {0: 1.0, 1: 0.5}.get(abs(ORDER_SLEEP[wanted] - ORDER_SLEEP[actual]), 0.0)


def _score_cleanliness(seeker, target):
    minimum, actual = seeker.reqs.get("min_cleanliness"), target.habits.get("cleanliness")
    if not minimum:
        return NOT_REQUIRED
    if not actual:
        return None
    return max(0.0, 1 - 0.25 * max(0, minimum - actual))


def _score_noise(seeker, target):
    maximum, actual = seeker.reqs.get("max_noise"), target.habits.get("noise")
    if not maximum:
        return NOT_REQUIRED
    if not actual:
        return None
    return max(0.0, 1 - 0.25 * max(0, actual - maximum))


def _score_guests(seeker, target):
    maximum, actual = seeker.reqs.get("guests", "any"), target.habits.get("guests")
    if maximum in ("any", "", None):
        return NOT_REQUIRED
    if actual not in ORDER_GUESTS:
        return None
    excess = max(0, ORDER_GUESTS[actual] - ORDER_GUESTS[maximum])
    return max(0.0, 1 - excess / 3)


def _score_smoking(seeker, target):
    rule, actual = seeker.reqs.get("smoking", "any"), target.habits.get("smoking")
    if rule in ("any", "", None):
        return NOT_REQUIRED
    if actual not in ("no", "outside", "inside"):
        return None
    if rule == "no_inside":
        return 0.0 if actual == "inside" else 1.0
    return {"no": 1.0, "outside": 0.4, "inside": 0.0}[actual]


def _score_pets(seeker, target):
    rule, actual = seeker.reqs.get("pets", "any"), target.habits.get("pets")
    if rule in ("any", "", None):
        return NOT_REQUIRED
    if actual not in ("none", "has"):
        return None
    return 0.0 if actual == "has" else 1.0


def _score_chores(seeker, target):
    wanted, actual = seeker.reqs.get("chores", "any"), target.habits.get("chores")
    if wanted in ("any", "", None):
        return NOT_REQUIRED
    if actual not in ORDER_CHORES:
        return None
    return {0: 1.0, 1: 0.5}.get(abs(ORDER_CHORES[wanted] - ORDER_CHORES[actual]), 0.0)


SCORERS = {
    "budget": _score_budget, "location": _score_location, "move_in": _score_move_in, "sleep": _score_sleep,
    "cleanliness": _score_cleanliness, "noise": _score_noise, "guests": _score_guests, "smoking": _score_smoking,
    "pets": _score_pets, "chores": _score_chores,
}


# ---------------------------------------------------------------- розрахунок пари

def directional_scores(seeker, target):
    """Оцінки за критеріями: наскільки target відповідає вимогам seeker. Значення: float | None | NOT_REQUIRED."""
    return {key: scorer(seeker, target) for key, scorer in SCORERS.items()}


def weighted_score(seeker, scores):
    """S = Σ(wᵢ·sᵢ) / Σwᵢ. Критерії «Неважливо» пропускаються, критерії без даних мають оцінку 0.5. None, якщо оцінювати нічого."""
    pairs = []
    for key, value in scores.items():
        if isinstance(value, float):
            pairs.append((seeker.weight(key), value))
        elif value is None:  # даних бракує: невідомо, а не збіг
            pairs.append((seeker.weight(key), NEUTRAL_SCORE))
    total_weight = sum(w for w, _ in pairs)
    if total_weight == 0:
        return None
    return sum(w * s for w, s in pairs) / total_weight


def mutual_score(score_ab, score_ba):
    if score_ab is None and score_ba is None:
        return None
    if score_ab is None or score_ba is None:
        return score_ab if score_ba is None else score_ba
    return MEAN_SHARE * (score_ab + score_ba) / 2 + MIN_SHARE * min(score_ab, score_ba)


@dataclass
class MatchOutcome:
    score: float | None            # 0..100
    score_ab: float | None
    score_ba: float | None
    coverage: int | None           # % критеріїв, для яких вистачило даних
    has_critical_conflict: bool
    critical_conflicts: list
    strengths: list
    concerns: list
    rows: list
    is_preliminary: bool

    def to_dict(self):
        return self.__dict__.copy()


def compare(me, other):
    """Порівнює «мене» з кандидатом. Усі побудовані пояснення — з точки зору me."""
    ab = directional_scores(me, other)      # мої вимоги → кандидат
    ba = directional_scores(other, me)      # вимоги кандидата → я
    s_ab, s_ba = weighted_score(me, ab), weighted_score(other, ba)
    final = mutual_score(s_ab, s_ba)

    rows, strengths, concerns, conflicts = [], [], [], []
    evaluated = missing = 0
    for key, label in LABELS.items():
        a, b = ab[key], ba[key]
        numeric = [(side, v) for side, v in (("you", a), ("candidate", b)) if isinstance(v, float)]
        if numeric:
            evaluated += 1
        elif a is None or b is None:
            missing += 1
        combined = min(v for _, v in numeric) if numeric else None
        worst_side = min(numeric, key=lambda item: item[1])[0] if numeric else None
        if len(numeric) == 2 and abs(numeric[0][1] - numeric[1][1]) < 0.01:
            worst_side = "both"

        status = "unknown"
        if combined is not None:
            status = "good" if combined >= STRENGTH_THRESHOLD else "bad" if combined < CONCERN_THRESHOLD else "mid"
            if status == "good":
                strengths.append(GOOD_TEXT[key])
            elif status == "bad":
                concerns.append(f"{BAD_TEXT[key]} ({SIDE_TEXT[worst_side]})")
        rows.append({"key": key, "label": label, "status": status,
                     "you_to_candidate": a if isinstance(a, float) else None,
                     "candidate_to_you": b if isinstance(b, float) else None,
                     "combined": combined, "weight_you": me.weight(key), "weight_candidate": other.weight(key)})

        for seeker, scores, side in ((me, ab, "you"), (other, ba, "candidate")):
            value = scores[key]
            if key in seeker.critical and isinstance(value, float) and value < CONFLICT_THRESHOLD:
                conflicts.append(f"{LABELS[key]}: {SIDE_TEXT[side]} критична вимога не виконується")
    if isinstance(ab["location"], float) and ab["location"] == 0.0 and not any(c.startswith(LABELS["location"]) for c in conflicts):
        conflicts.append("Місто та район: кандидат шукає в іншому місті")

    known = evaluated + missing
    coverage = round(100 * evaluated / known) if known else None
    if evaluated == 0:  # нічого реально порівняти: не вигадуємо оцінку
        s_ab = s_ba = final = None
    return MatchOutcome(
        score=None if final is None else round(final * 100, 1),
        score_ab=None if s_ab is None else round(s_ab * 100, 1),
        score_ba=None if s_ba is None else round(s_ba * 100, 1),
        coverage=coverage, has_critical_conflict=bool(conflicts), critical_conflicts=conflicts,
        strengths=strengths, concerns=concerns, rows=rows,
        is_preliminary=final is None or (coverage is not None and coverage < PRELIMINARY_COVERAGE))


# ---------------------------------------------------------------- робота з БД

def build_snapshot(profile):
    """Збирає Snapshot із профілю (використовуйте select_related/prefetch_related для швидкодії)."""
    lifestyle = getattr(profile, "lifestyle", None)
    search = getattr(profile, "search", None)
    listings = [l for l in profile.user.housing_listings.all() if l.is_active and not l.is_hidden]
    weights = list(profile.weights.all())
    return Snapshot(
        user_id=profile.user_id, name=profile.display_name,
        city=(search.city if search and search.city else profile.city),
        district=search.district if search else "",
        budget_min=search.budget_min if search else None, budget_max=search.budget_max if search else None,
        move_in=(search.move_in_date if search and search.move_in_date else profile.move_in_date),
        habits={"sleep": getattr(lifestyle, "sleep_schedule", ""), "cleanliness": getattr(lifestyle, "cleanliness", None),
                "noise": getattr(lifestyle, "noise_level", None), "guests": getattr(lifestyle, "guests_frequency", ""),
                "smoking": getattr(lifestyle, "smoking", ""), "pets": getattr(lifestyle, "pets", ""),
                "chores": getattr(lifestyle, "chores_attitude", "")},
        reqs={"sleep": getattr(search, "req_sleep", "any"), "min_cleanliness": getattr(search, "req_min_cleanliness", None),
              "max_noise": getattr(search, "req_max_noise", None), "guests": getattr(search, "req_guests", "any"),
              "smoking": getattr(search, "req_smoking", "any"), "pets": getattr(search, "req_pets", "any"),
              "chores": getattr(search, "req_chores", "any")},
        weights={w.criterion: w.weight for w in weights},
        critical={w.criterion for w in weights if w.is_critical},
        listing=({"city": listings[0].city, "district": listings[0].district, "price": listings[0].price_per_person}
                 if listings else None))


def profile_queryset():
    from profiles.models import Profile
    return (Profile.objects.select_related("user", "lifestyle", "search").prefetch_related(
        "weights", Prefetch("user__housing_listings", queryset=HousingListing.objects.all())))


def candidate_profiles(user):
    """Профілі, які можна рекомендувати користувачу: активні, не він сам, без блокувань."""
    return (profile_queryset().filter(is_active_search=True, user__is_active=True)
            .exclude(user=user).exclude(user_id__in=blocked_user_ids(user)))


def save_result(user, candidate_user, outcome):
    to_decimal = lambda v: v  # noqa: E731
    MatchResult.objects.update_or_create(
        user=user, candidate=candidate_user,
        defaults={"score": to_decimal(outcome.score), "score_user_to_candidate": outcome.score_ab,
                  "score_candidate_to_user": outcome.score_ba, "data_coverage": outcome.coverage,
                  "has_critical_conflict": outcome.has_critical_conflict, "details": outcome.to_dict()})


def get_recommendations(user):
    """Повертає список (profile, outcome), впорядкований за спаданням сумісності.

    Спочатку кандидати без критичних конфліктів, потім — з конфліктами. Без оцінки (None) — в кінці."""
    me = build_snapshot(profile_queryset().get(user=user))
    results = []
    for profile in candidate_profiles(user):
        outcome = compare(me, build_snapshot(profile))
        results.append((profile, outcome))
        save_result(user, profile.user, outcome)
    results.sort(key=lambda item: (item[1].has_critical_conflict, item[1].score is None, -(item[1].score or 0)))
    return results


def get_match(user, candidate_profile):
    me = build_snapshot(profile_queryset().get(user=user))
    outcome = compare(me, build_snapshot(profile_queryset().get(pk=candidate_profile.pk)))
    save_result(user, candidate_profile.user, outcome)
    return outcome
