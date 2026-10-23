from django import forms

from config.forms import StyledFormMixin
from profiles.models import Profile


class RecommendationFilterForm(StyledFormMixin, forms.Form):
    mode = forms.ChoiceField(label="Хто шукає", required=False,
                             choices=[("", "Усі")] + list(Profile.Mode.choices))
    city = forms.CharField(label="Місто", required=False, widget=forms.TextInput(attrs={"placeholder": "напр. Львів"}))
    min_score = forms.IntegerField(label="Сумісність від, %", required=False, min_value=0, max_value=100)
    max_budget = forms.IntegerField(label="Бюджет кандидата до, грн", required=False, min_value=1,
                                    widget=forms.NumberInput(attrs={"placeholder": "напр. 8000", "min": 1}))
    sort = forms.ChoiceField(label="Сортування", required=False,
                             choices=[("", "За сумісністю"), ("budget", "За бюджетом: від меншого"), ("name", "За ім’ям")])
    only_housing = forms.BooleanField(label="Лише з житлом", required=False)
    show_conflicts = forms.BooleanField(label="Показувати кандидатів із критичними конфліктами", required=False)
