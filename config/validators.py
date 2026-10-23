import os

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_file(file):
    """Перевіряє розмір, розширення та вміст зображення."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Дозволені формати зображень: JPG, PNG, WEBP.")
    if file.size > settings.MAX_IMAGE_SIZE:
        limit = settings.MAX_IMAGE_SIZE // (1024 * 1024)
        raise ValidationError(f"Файл завеликий. Максимальний розмір — {limit} МБ.")
    try:
        file.seek(0)
        Image.open(file).verify()
    except Exception:
        raise ValidationError("Файл пошкоджений або не є зображенням.")
    finally:
        file.seek(0)
