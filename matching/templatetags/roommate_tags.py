"""Власні теги шаблонів Roommate: відображення оцінки сумісності."""
from django import template

register = template.Library()

GOOD_THRESHOLD = 75
MID_THRESHOLD = 50


@register.simple_tag
def score_level(score):
    """CSS-модифікатор для оцінки сумісності: '' (≥75), 'mid' (≥50), 'low' (нижче)."""
    if score is None:
        return ""
    if score >= GOOD_THRESHOLD:
        return ""
    return "mid" if score >= MID_THRESHOLD else "low"


@register.inclusion_tag("components/score_ring.html")
def score_ring(score, size=""):
    """Кільце сумісності. Без оцінки показує прочерк. size: '' | 'sm' | 'lg'."""
    has_score = score is not None
    classes = " ".join(part for part in ("ring", size, score_level(score) if has_score else "") if part)
    return {"has_score": has_score, "score": score, "classes": classes}
