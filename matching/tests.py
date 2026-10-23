from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from housing.models import HousingListing
from interactions.models import UserBlock
from profiles.models import CriterionWeight, LifestylePreference, SearchPreference

from . import services
from .services import Snapshot, compare, mutual_score, weighted_score

User = get_user_model()


def snap(user_id=1, **kw):
    base = dict(user_id=user_id, city="Львів", budget_min=5000, budget_max=8000, move_in=date(2026, 9, 1),
                habits={"sleep": "early", "cleanliness": 5, "noise": 2, "guests": "sometimes", "smoking": "no",
                        "pets": "none", "chores": "split"},
                reqs={"sleep": "any", "min_cleanliness": None, "max_noise": None, "guests": "any", "smoking": "any",
                      "pets": "any", "chores": "any"})
    base.update(kw)
    return Snapshot(**base)


class FormulaTests(SimpleTestCase):
    def test_weighted_score_formula(self):
        s = snap(weights={"noise": 5, "cleanliness": 1})
        self.assertAlmostEqual(weighted_score(s, {"noise": 1.0, "cleanliness": 0.0}), 5 / 6)

    def test_not_required_is_skipped_and_missing_data_is_neutral(self):
        # «Неважливо» не враховується взагалі
        self.assertIsNone(weighted_score(snap(), {"noise": "not_required"}))
        # відсутні дані — нейтральні 0.5 (невідомо), а не збіг
        self.assertEqual(weighted_score(snap(), {"noise": "not_required", "sleep": None}), 0.5)
        self.assertAlmostEqual(weighted_score(snap(), {"noise": 1.0, "sleep": None}), 0.75)

    def test_mutual_penalizes_one_sided_fit(self):
        self.assertLess(mutual_score(1.0, 0.2), (1.0 + 0.2) / 2)
        self.assertAlmostEqual(mutual_score(0.8, 0.8), 0.8)

    def test_mutual_with_single_direction(self):
        self.assertEqual(mutual_score(0.7, None), 0.7)
        self.assertIsNone(mutual_score(None, None))


class CriteriaTests(SimpleTestCase):
    def test_identical_profiles_score_high(self):
        a = snap(1, reqs={**snap().reqs, "sleep": "early", "min_cleanliness": 4, "max_noise": 3})
        b = snap(2)
        b.reqs = dict(a.reqs, sleep="early")
        outcome = compare(a, b)
        self.assertGreaterEqual(outcome.score, 95)
        self.assertFalse(outcome.has_critical_conflict)

    def test_budget_overlap_and_gap(self):
        from .services import _score_budget
        self.assertEqual(_score_budget(snap(budget_min=5000, budget_max=8000), snap(budget_min=5000, budget_max=8000)), 1.0)
        far = _score_budget(snap(budget_min=3000, budget_max=4000), snap(budget_min=9000, budget_max=12000))
        self.assertEqual(far, 0.0)
        near = _score_budget(snap(budget_min=5000, budget_max=6000), snap(budget_min=6100, budget_max=8000))
        self.assertTrue(0 < near < 0.6)

    def test_listing_price_replaces_budget_range(self):
        owner = snap(2, listing={"city": "Львів", "district": "", "price": 6500})
        seeker = snap(1, budget_min=5000, budget_max=8000)
        from .services import _score_budget
        self.assertEqual(_score_budget(seeker, owner), 1.0)

    def test_different_city_is_critical_conflict(self):
        outcome = compare(snap(1), snap(2, city="Київ"))
        self.assertTrue(outcome.has_critical_conflict)

    def test_critical_smoking_conflict_even_with_high_score(self):
        a = snap(1, critical={"smoking"}, reqs={**snap().reqs, "smoking": "no_inside"})
        b = snap(2, habits={**snap().habits, "smoking": "inside"})
        outcome = compare(a, b)
        self.assertTrue(outcome.has_critical_conflict)
        self.assertTrue(any("Куріння" in c for c in outcome.critical_conflicts))

    def test_noncritical_smoking_conflict_not_blocking(self):
        a = snap(1, reqs={**snap().reqs, "smoking": "no_inside"})
        b = snap(2, habits={**snap().habits, "smoking": "inside"})
        outcome = compare(a, b)
        self.assertFalse(outcome.has_critical_conflict)
        self.assertTrue(any("куріння" in c.lower() for c in outcome.concerns))

    def test_candidate_critical_requirement_also_checked(self):
        a = snap(1, habits={**snap().habits, "pets": "has"})
        b = snap(2, critical={"pets"}, reqs={**snap().reqs, "pets": "no_pets"})
        self.assertTrue(compare(a, b).has_critical_conflict)

    def test_weights_change_result(self):
        reqs = {**snap().reqs, "max_noise": 1, "min_cleanliness": 1}
        noisy = snap(2, habits={**snap().habits, "noise": 5})
        low = compare(snap(1, reqs=reqs, weights={"noise": 5, "cleanliness": 1}), noisy).score
        high = compare(snap(1, reqs=reqs, weights={"noise": 1, "cleanliness": 5}), noisy).score
        self.assertLess(low, high)

    def test_partial_profile_handled(self):
        empty = Snapshot(user_id=3)
        outcome = compare(snap(1, reqs={**snap().reqs, "sleep": "early"}), empty)
        self.assertTrue(outcome.is_preliminary)
        outcome_none = compare(Snapshot(user_id=4), Snapshot(user_id=5))
        self.assertIsNone(outcome_none.score)
        self.assertTrue(outcome_none.is_preliminary)

    def test_incomplete_profile_cannot_get_perfect_score(self):
        """D-01: збіг за кількома заповненими полями не дає 100%, якщо решта даних невідома."""
        me = snap(1, reqs={**snap().reqs, "sleep": "early", "min_cleanliness": 4, "max_noise": 3, "guests": "sometimes",
                           "smoking": "no_inside", "pets": "no_pets", "chores": "split"})
        sparse = Snapshot(user_id=2, city="Львів", district="Франківський", budget_min=5000, budget_max=8000)
        outcome = compare(me, sparse)
        self.assertTrue(outcome.is_preliminary)
        self.assertEqual(outcome.coverage, 20)
        self.assertLess(outcome.score, 75)
        self.assertGreater(outcome.score, 50)  # невідомість не карається як конфлікт
        self.assertFalse(outcome.has_critical_conflict)

    def test_missing_data_is_not_a_critical_conflict(self):
        me = snap(1, critical={"smoking"}, reqs={**snap().reqs, "smoking": "no_inside"})
        sparse = Snapshot(user_id=2, city="Львів", district="Франківський", budget_min=5000, budget_max=8000)
        self.assertFalse(compare(me, sparse).has_critical_conflict)

    def test_nothing_comparable_gives_no_score(self):
        outcome = compare(snap(1, city="", district="", budget_min=None, budget_max=None, move_in=None), Snapshot(user_id=2))
        self.assertIsNone(outcome.score)
        self.assertIsNone(outcome.score_ab)

    def test_any_requirements_do_not_lower_coverage(self):
        outcome = compare(snap(1), snap(2))
        self.assertEqual(outcome.coverage, 100)

    def test_result_is_deterministic(self):
        a, b = snap(1, reqs={**snap().reqs, "max_noise": 2}), snap(2)
        self.assertEqual(compare(a, b).to_dict(), compare(a, b).to_dict())

    def test_score_within_bounds(self):
        outcome = compare(snap(1, reqs={**snap().reqs, "max_noise": 1, "sleep": "late", "pets": "no_pets"}),
                          snap(2, habits={**snap().habits, "noise": 5, "pets": "has"}))
        self.assertTrue(0 <= outcome.score <= 100)

    def test_explanations_contain_strengths_and_concerns(self):
        a = snap(1, reqs={**snap().reqs, "guests": "never", "min_cleanliness": 3})
        b = snap(2, habits={**snap().habits, "guests": "often"})
        outcome = compare(a, b)
        self.assertTrue(any("Бюджет" in s for s in outcome.strengths))
        self.assertTrue(any("гост" in c.lower() for c in outcome.concerns))


class RecommendationDbTests(TestCase):
    def make_user(self, email, name, **lifestyle):
        user = User.objects.create_user(email, "Sup3r-secret-pass", first_name=name, last_name="Т")
        profile = user.profile
        profile.city = "Львів"
        profile.save()
        LifestylePreference.objects.create(profile=profile, **lifestyle)
        SearchPreference.objects.create(profile=profile, city="Львів", budget_min=5000, budget_max=8000)
        return user

    def setUp(self):
        self.me = self.make_user("me@example.com", "Я", sleep_schedule="early", cleanliness=5, noise_level=2, smoking="no", pets="none")
        self.good = self.make_user("good@example.com", "Добрий", sleep_schedule="early", cleanliness=5, noise_level=2, smoking="no", pets="none")
        self.smoker = self.make_user("smoker@example.com", "Курець", sleep_schedule="early", cleanliness=5, noise_level=2, smoking="inside", pets="none")
        me_search = self.me.profile.search
        me_search.req_smoking = "no_inside"
        me_search.save()
        CriterionWeight.objects.create(profile=self.me.profile, criterion="smoking", weight=5, is_critical=True)

    def test_recommendations_exclude_self_and_put_conflicts_last(self):
        results = services.get_recommendations(self.me)
        ids = [p.user_id for p, _ in results]
        self.assertNotIn(self.me.pk, ids)
        self.assertEqual(ids[0], self.good.pk)
        self.assertEqual(ids[-1], self.smoker.pk)
        self.assertTrue(results[-1][1].has_critical_conflict)

    def test_results_saved_to_match_table(self):
        services.get_recommendations(self.me)
        from .models import MatchResult
        self.assertEqual(MatchResult.objects.filter(user=self.me).count(), 2)

    def test_blocked_and_inactive_excluded(self):
        UserBlock.objects.create(blocker=self.good, blocked=self.me)
        self.smoker.profile.is_active_search = False
        self.smoker.profile.save()
        self.assertEqual(services.get_recommendations(self.me), [])

    def test_listing_marks_housing_and_used_in_price(self):
        HousingListing.objects.create(owner=self.good, title="Кімната", city="Львів", price_per_person=6500, description="x")
        self.client.force_login(self.me)
        response = self.client.get(reverse("matching:recommendations"))
        self.assertContains(response, "Має житло")

    def test_recommendations_page_hides_conflicts_by_default(self):
        self.client.force_login(self.me)
        response = self.client.get(reverse("matching:recommendations"))
        self.assertContains(response, "Добрий")
        self.assertNotContains(response, "Курець")
        response = self.client.get(reverse("matching:recommendations"), {"show_conflicts": "on"})
        self.assertContains(response, "Курець")
        self.assertContains(response, "Критичний конфлікт")

    def test_candidate_page_shows_explanation_but_not_email(self):
        self.client.force_login(self.me)
        response = self.client.get(reverse("matching:candidate", args=[self.good.profile.pk]))
        self.assertContains(response, "Сильні сторони")
        self.assertNotContains(response, "good@example.com")

    def test_blocked_candidate_page_404(self):
        UserBlock.objects.create(blocker=self.me, blocked=self.good)
        self.client.force_login(self.me)
        self.assertEqual(self.client.get(reverse("matching:candidate", args=[self.good.profile.pk])).status_code, 404)


class FilterAndSortTests(TestCase):
    """D-02: фільтр за бюджетом і вибір сортування у списку рекомендацій."""

    def make(self, email, name, low, high):
        user = User.objects.create_user(email, "Sup3r-secret-pass", first_name=name, last_name="Т")
        user.profile.city = "Львів"
        user.profile.save()
        LifestylePreference.objects.create(profile=user.profile, cleanliness=4)
        SearchPreference.objects.create(profile=user.profile, city="Львів", budget_min=low, budget_max=high)
        return user

    def setUp(self):
        self.me = self.make("me@example.com", "Я", 5000, 8000)
        self.cheap = self.make("c@example.com", "Борис", 4000, 6000)
        self.mid = self.make("m@example.com", "Антон", 6000, 9000)
        self.rich = self.make("r@example.com", "Віктор", 12000, 15000)
        self.client.force_login(self.me)

    def names(self, **params):
        response = self.client.get(reverse("matching:recommendations"), params)
        return [p.display_name for p, _ in response.context["page"]]

    def test_budget_filter_hides_candidates_above_limit(self):
        self.assertEqual(set(self.names()), {"Борис", "Антон", "Віктор"})
        self.assertEqual(set(self.names(max_budget=8000)), {"Борис", "Антон"})
        self.assertEqual(set(self.names(max_budget=4000)), {"Борис"})

    def test_budget_filter_uses_listing_price(self):
        HousingListing.objects.create(owner=self.rich, title="Кімната", city="Львів", price_per_person=6500, description="x")
        self.assertIn("Віктор", self.names(max_budget=7000))

    def test_sort_by_budget_and_name(self):
        self.assertEqual(self.names(sort="budget"), ["Борис", "Антон", "Віктор"])
        self.assertEqual(self.names(sort="name"), ["Антон", "Борис", "Віктор"])

    def test_default_sort_is_compatibility_and_invalid_sort_rejected(self):
        response = self.client.get(reverse("matching:recommendations"), {"sort": "hack"})
        self.assertIn("sort", response.context["form"].errors)
        scores = [o.score for _, o in self.client.get(reverse("matching:recommendations")).context["page"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_name_sort_follows_ukrainian_alphabet(self):
        """«І» має стояти між «З» і «Й», а не в кінці списку, як за кодами Unicode."""
        for email, name in (("g@e.com", "Ганна"), ("i@e.com", "Ігор"), ("o@e.com", "Олена"), ("e@e.com", "Єва"), ("z@e.com", "Зоя")):
            self.make(email, name, 5000, 8000)
        ordered = self.names(sort="name")
        expected = ["Антон", "Борис", "Віктор", "Ганна", "Єва", "Зоя", "Ігор", "Олена"]
        self.assertEqual(ordered, expected)


class CriticalConflictSearchRegressionTests(TestCase):
    """Регресія: галочка «Показувати кандидатів із критичними конфліктами» і підрахунки на /people/.

    Причина помилки: `filters = form.cleaned_data if form.is_valid() else {}` відкидав УСІ фільтри (і галочку),
    якщо хоч одне поле було некоректним, а форма все одно малювала галочку ввімкненою.
    Позначення TC-NEW-nn відповідає docs/testing/10_regression_tc_new.md."""

    def make(self, email, name, smoking="no", city="Львів", low=5000, high=8000, mode="joint"):
        user = User.objects.create_user(email, "Sup3r-secret-pass", first_name=name, last_name="Т")
        profile = user.profile
        profile.city, profile.search_mode = city, mode
        profile.save()
        LifestylePreference.objects.create(profile=profile, sleep_schedule="early", cleanliness=5, noise_level=2,
                                           guests_frequency="sometimes", smoking=smoking, pets="none", chores_attitude="split")
        SearchPreference.objects.create(profile=profile, city=city, budget_min=low, budget_max=high, req_smoking="no_inside")
        return user

    def setUp(self):
        self.me = self.make("me@example.com", "Я")
        CriterionWeight.objects.create(profile=self.me.profile, criterion="smoking", weight=5, is_critical=True)
        self.good = self.make("good@example.com", "Добрий")
        self.smoker = self.make("smoker@example.com", "Курець", smoking="inside")
        self.client.force_login(self.me)
        self.url = reverse("matching:recommendations")

    def get(self, **params):
        return self.client.get(self.url, params)

    @staticmethod
    def card_names(response):
        import re
        return re.findall(r'class="cand-name"><a [^>]*>([^<]+)<', response.content.decode())

    def checkbox_checked(self, response):
        import re
        return bool(re.search(r'<input[^>]*name="show_conflicts"[^>]*checked|<input[^>]*checked[^>]*name="show_conflicts"', response.content.decode()))

    # TC-NEW-01
    def test_candidate_without_conflict_is_shown_by_default(self):
        response = self.get()
        self.assertEqual(self.card_names(response), ["Добрий"])
        self.assertEqual(response.context["found_total"], 1)

    # TC-NEW-02
    def test_conflicting_candidate_hidden_when_checkbox_off(self):
        response = self.get()
        self.assertNotIn("Курець", self.card_names(response))
        self.assertEqual(response.context["hidden_conflicts"], 1)
        self.assertEqual(response.context["conflicted"], [])

    # TC-NEW-03
    def test_conflicting_candidate_shown_with_warning_when_checkbox_on(self):
        response = self.get(show_conflicts="on")
        self.assertEqual(self.card_names(response), ["Добрий", "Курець"])
        self.assertContains(response, "З критичними конфліктами (1)")
        self.assertContains(response, "Критичний конфлікт")
        outcome = response.context["conflicted"][0][1]
        self.assertTrue(outcome.has_critical_conflict)
        self.assertTrue(any("Куріння" in c for c in outcome.critical_conflicts))

    # TC-NEW-04
    def test_checkbox_state_is_kept_after_apply(self):
        self.assertTrue(self.checkbox_checked(self.get(show_conflicts="on")))
        self.assertFalse(self.checkbox_checked(self.get()))
        self.assertTrue(self.checkbox_checked(self.get(show_conflicts="on", city="Львів", min_score=0)))

    def test_invalid_other_filter_does_not_drop_checkbox(self):
        """Саме цей сценарій давав на екрані: галочка ввімкнена, але кандидатів 0 і підказка «увімкніть галочку»."""
        for params in ({"max_budget": 0}, {"min_score": 150}, {"sort": "x"}, {"max_budget": "abc"}):
            response = self.get(show_conflicts="on", **params)
            self.assertTrue(self.checkbox_checked(response), params)
            self.assertEqual(self.card_names(response), ["Добрий", "Курець"], params)
            self.assertEqual(response.context["found_total"], 2, params)
            self.assertContains(response, "Не застосовано через помилку в полі", msg_prefix=str(params))
            self.assertNotContains(response, "Увімкніть", msg_prefix=str(params))
            self.assertEqual(response.context["hidden_conflicts"], 0, params)

    def test_valid_filters_still_apply_when_another_field_is_invalid(self):
        response = self.get(show_conflicts="on", city="Київ", max_budget=0)
        self.assertEqual(self.card_names(response), [])
        self.assertContains(response, "У місті «Київ» кандидатів не знайдено")

    # TC-NEW-05
    def test_found_count_matches_rendered_cards(self):
        for params in ({}, {"show_conflicts": "on"}, {"city": "Львів"}, {"show_conflicts": "on", "max_budget": 6000},
                       {"show_conflicts": "on", "min_score": 100}, {"only_housing": "on", "show_conflicts": "on"}):
            response = self.get(**params)
            self.assertEqual(response.context["found_total"], len(self.card_names(response)), params)
            self.assertContains(response, f"Знайдено: <strong>{response.context['found_total']}</strong>")

    # TC-NEW-06
    def test_hidden_notice_matches_filter_state(self):
        off = self.get()
        self.assertContains(off, "Ще 1 кандидат(ів) приховано через критичні конфлікти")
        self.assertContains(off, "show_conflicts=on")  # посилання-вмикач, а не прохання поставити галочку
        on = self.get(show_conflicts="on")
        self.assertNotContains(on, "приховано через критичні конфлікти")
        self.assertNotContains(on, "Увімкніть")
        self.smoker.delete()
        self.assertNotContains(self.get(), "приховано через критичні конфлікти")

    def test_notice_counts_only_candidates_passing_other_filters(self):
        response = self.get(city="Київ")
        self.assertEqual(response.context["hidden_conflicts"], 0)
        self.assertNotContains(response, "Ще 1 кандидат")

    # TC-NEW-07
    def test_empty_state_explains_reason(self):
        self.assertContains(self.get(city="Одеса"), "У місті «Одеса» кандидатів не знайдено (до фільтра за містом було 2)")
        self.assertContains(self.get(max_budget=1000), "Мінімальний бюджет усіх 2 кандидатів вищий за 1000 грн")
        self.assertContains(self.get(min_score=100, show_conflicts="on"), "Жоден із 2 кандидатів не має сумісності від 100%")
        self.assertContains(self.get(only_housing="on"), "не має активного оголошення")
        self.assertContains(self.get(mode="has_housing"), "не має режиму «Маю житло, шукаю співмешканця»")

    def test_empty_state_when_only_conflicting_candidates_exist(self):
        self.good.delete()
        response = self.get()
        self.assertContains(response, "мають критичні конфлікти")
        self.assertContains(response, "Показати кандидатів із конфліктами")
        shown = self.get(show_conflicts="on")
        self.assertEqual(self.card_names(shown), ["Курець"])
        self.assertNotContains(shown, "Підходящих кандидатів поки немає")
        self.assertContains(shown, "Кандидатів без критичних конфліктів немає")

    def test_empty_state_when_no_other_profiles(self):
        self.good.delete()
        self.smoker.delete()
        self.assertContains(self.get(), "Поки немає інших активних профілів")

    # TC-NEW-08
    def test_candidate_is_not_duplicated(self):
        for k in range(2):
            HousingListing.objects.create(owner=self.good, title=f"Кімната {k}", city="Львів", price_per_person=6000, description="x")
        for params in ({}, {"only_housing": "on"}, {"show_conflicts": "on"}):
            names = self.card_names(self.get(**params))
            self.assertEqual(len(names), len(set(names)), params)
        self.assertEqual(self.card_names(self.get(only_housing="on")), ["Добрий"])

    # TC-NEW-09
    def test_changing_weights_does_not_break_filters(self):
        before = self.card_names(self.get(show_conflicts="on", city="Львів"))
        for key, weight in (("noise", 5), ("budget", 1), ("cleanliness", 5)):
            CriterionWeight.objects.update_or_create(profile=self.me.profile, criterion=key, defaults={"weight": weight})
        response = self.get(show_conflicts="on", city="Львів")
        self.assertEqual(self.card_names(response), before)
        self.assertEqual(self.card_names(self.get(city="Київ", show_conflicts="on")), [])
        self.assertEqual(self.card_names(self.get()), ["Добрий"])  # критичність куріння збережена
        CriterionWeight.objects.filter(profile=self.me.profile, criterion="smoking").update(is_critical=False)
        self.assertEqual(set(self.card_names(self.get())), {"Добрий", "Курець"})

    # TC-NEW-10
    def test_own_profile_never_listed(self):
        for params in ({}, {"show_conflicts": "on"}, {"city": "Львів", "show_conflicts": "on", "sort": "name"}):
            self.assertNotIn("Я", self.card_names(self.get(**params)), params)

    # TC-NEW-11
    def test_reload_gives_same_result_and_state(self):
        params = {"show_conflicts": "on", "city": "Львів", "sort": "name"}
        first, second = self.get(**params), self.get(**params)
        self.assertEqual(self.card_names(first), self.card_names(second))
        self.assertEqual(first.context["found_total"], second.context["found_total"])
        self.assertTrue(self.checkbox_checked(second))
        # без параметрів у URL сервер віддає вимкнений стан; форма заборонює відновлення стану браузером
        self.assertContains(self.get(), 'autocomplete="off"')

    def test_pagination_links_keep_checkbox_parameter(self):
        for k in range(10):
            self.make(f"bulk{k}@example.com", f"Масовий{k}")
        response = self.get(show_conflicts="on")
        self.assertEqual(response.context["page"].paginator.num_pages, 2)
        self.assertContains(response, "show_conflicts=on&page=2")
        page2 = self.get(show_conflicts="on", page=2)
        self.assertTrue(self.checkbox_checked(page2))
        self.assertContains(page2, "Курець")  # секція конфліктів не губиться на другій сторінці

    # TC-NEW-12 (розмітка й CSS; це НЕ візуальна перевірка на пристрої)
    def test_markup_is_mobile_friendly(self):
        from pathlib import Path
        from django.conf import settings
        response = self.get(show_conflicts="on")
        self.assertContains(response, 'name="viewport" content="width=device-width, initial-scale=1"')
        self.assertContains(response, 'class="grid grid-3"')
        self.assertNotContains(response, 'style="grid-template-columns')
        css = (Path(settings.BASE_DIR) / "static/css/main.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:620px){.grid-2,.grid-3{grid-template-columns:1fr}}", css)
        self.assertIn("repeat(auto-fit,minmax(170px,1fr))", css)

    def test_other_filters_keep_working_together_with_conflicts(self):
        HousingListing.objects.create(owner=self.smoker, title="Кімната", city="Львів", price_per_person=6000, description="x")
        self.assertEqual(self.card_names(self.get(show_conflicts="on", only_housing="on")), ["Курець"])
        self.assertEqual(self.card_names(self.get(show_conflicts="on", min_score=100)), [])
        self.assertEqual(self.card_names(self.get(show_conflicts="on", sort="name")), ["Добрий", "Курець"])


class FilterLayoutTests(TestCase):
    """Фільтри: поля в одній сітці, чекбокси й кнопка — в окремому рядку під сіткою."""

    def setUp(self):
        self.user = User.objects.create_user("f@example.com", "Sup3r-secret-pass", first_name="Ф", last_name="Т")
        self.client.force_login(self.user)

    def html(self):
        return self.client.get(reverse("matching:recommendations")).content.decode()

    def test_checkboxes_and_button_live_in_footer_row(self):
        html = self.html()
        grid, foot = html.split('class="filters-foot"', 1)
        grid = grid.split('class="filters"', 1)[1]
        self.assertNotIn('type="checkbox"', grid)
        self.assertEqual(foot.count('type="checkbox"'), 2)
        self.assertLess(foot.index('type="checkbox"'), foot.index("Застосувати"))
        for label in ("Хто шукає", "Місто", "Сумісність від, %", "Бюджет кандидата до, грн", "Сортування"):
            self.assertIn(label, grid)

    def test_budget_field_has_no_help_text_that_breaks_the_grid(self):
        html = self.html()
        self.assertNotIn("Показати тих, чия мінімальна сума", html)
        self.assertIn('placeholder="напр. 8000"', html)

    def test_filter_css_is_responsive(self):
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / "static/css/main.css").read_text(encoding="utf-8")
        for rule in (".filters-foot{", ".filters-checks{", "repeat(auto-fit,minmax(170px,1fr))", "@media(max-width:620px){.filters-checks{"):
            self.assertIn(rule, css)
