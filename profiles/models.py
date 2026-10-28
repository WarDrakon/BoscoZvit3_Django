from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from config.person_validators import display_name_validator, validate_birth_date
from config.validators import validate_image_file

# Критерії, за якими система порівнює двох користувачів
CRITERIA = [
    ("budget", "Бюджет"),
    ("location", "Місто та район"),
    ("move_in", "Дата заселення"),
    ("age", "Вік"),
    ("sleep", "Режим сну"),
    ("cleanliness", "Чистота"),
    ("noise", "Рівень шуму"),
    ("guests", "Гості"),
    ("smoking", "Куріння"),
    ("pets", "Домашні тварини"),
    ("chores", "Побутові обов’язки"),
]
CRITERIA_LABELS = dict(CRITERIA)

SCALE_1_5 = [MinValueValidator(1), MaxValueValidator(5)]


class Profile(models.Model):
    class Mode(models.TextChoices):
        JOINT = "joint", "Шукаю житло разом зі співмешканцем"
        HAS_HOUSING = "has_housing", "Маю житло, шукаю співмешканця"

    profile_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField("Публічне ім’я", max_length=60, validators=[display_name_validator])
    photo = models.ImageField("Фотографія", upload_to="profiles/", blank=True, validators=[validate_image_file])
    city = models.CharField("Місто", max_length=100, blank=True)
    occupation = models.CharField("Рід занять", max_length=120, blank=True)
    about = models.TextField("Про себе", max_length=1000, blank=True)
    search_mode = models.CharField("Режим пошуку", max_length=20, choices=Mode.choices, default=Mode.JOINT)
    birth_date = models.DateField("Дата народження", null=True, blank=True, validators=[validate_birth_date])
    move_in_date = models.DateField("Орієнтовна дата заселення", null=True, blank=True)
    is_active_search = models.BooleanField("Я зараз шукаю співмешканця", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "профіль"
        verbose_name_plural = "профілі"
        indexes = [models.Index(fields=["city", "is_active_search"])]

    def __str__(self):
        return self.display_name

    def get_absolute_url(self):
        return reverse("matching:candidate", kwargs={"profile_id": self.pk})

    @property
    def age(self):
        """Повні роки на поточну дату. None, якщо дата народження не вказана."""
        if not self.birth_date:
            return None
        today = date.today()
        return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))

    @property
    def age_text(self):
        """«22 роки» або None, якщо дата народження не вказана (для «Марія, 22 роки»)."""
        age = self.age
        return None if age is None else years_ua(age)

    @property
    def age_label(self):
        """«22 роки» або «Вік не вказано»."""
        return self.age_text or "Вік не вказано"


def years_ua(n):
    """«1 рік», «22 роки», «25 років», «11 років»."""
    if 11 <= n % 100 <= 14:
        word = "років"
    else:
        word = {1: "рік", 2: "роки", 3: "роки", 4: "роки"}.get(n % 10, "років")
    return f"{n} {word}"


class LifestylePreference(models.Model):
    """Фактичні побутові звички користувача. Поля можна залишати порожніми."""

    SLEEP = [("early", "Раннє пробудження (жайворонок)"), ("regular", "Звичайний режим"), ("late", "Пізнє лягання (сова)")]
    GUESTS = [("never", "Не приймаю гостей"), ("rare", "Рідко"), ("sometimes", "Іноді"), ("often", "Часто")]
    SMOKING = [("no", "Не курю"), ("outside", "Курю лише поза приміщенням"), ("inside", "Курю в приміщенні")]
    PETS = [("none", "Немає тварин"), ("has", "Є домашні тварини")]
    SCHEDULE = [("office", "Робота в офісі"), ("remote", "Віддалена робота"), ("study", "Навчання"),
                ("shift", "Позмінний графік"), ("flexible", "Гнучкий графік")]
    CHORES = [("split", "Рівний розподіл обов’язків"), ("flexible", "Гнучко, за домовленістю"),
              ("minimal", "Мінімальна участь")]

    lifestyle_id = models.AutoField(primary_key=True)
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="lifestyle")
    sleep_schedule = models.CharField("Режим сну", max_length=10, choices=SLEEP, blank=True)
    cleanliness = models.PositiveSmallIntegerField("Рівень охайності (1–5)", null=True, blank=True, validators=SCALE_1_5)
    noise_level = models.PositiveSmallIntegerField("Звичний рівень шуму (1–5)", null=True, blank=True, validators=SCALE_1_5)
    guests_frequency = models.CharField("Прийом гостей", max_length=10, choices=GUESTS, blank=True)
    smoking = models.CharField("Куріння", max_length=10, choices=SMOKING, blank=True)
    pets = models.CharField("Домашні тварини", max_length=10, choices=PETS, blank=True)
    work_schedule = models.CharField("Робочий або навчальний графік", max_length=10, choices=SCHEDULE, blank=True)
    chores_attitude = models.CharField("Побутові обов’язки", max_length=10, choices=CHORES, blank=True)

    class Meta:
        verbose_name = "побутові звички"
        verbose_name_plural = "побутові звички"

    def __str__(self):
        return f"Звички: {self.profile}"


class SearchPreference(models.Model):
    """Вимоги до потенційного співмешканця та параметри пошуку. «Неважливо» = порожнє значення / any."""

    SLEEP = [("any", "Неважливо")] + LifestylePreference.SLEEP
    GUESTS = [("any", "Неважливо"), ("never", "Не приймає гостей"), ("rare", "Не частіше ніж рідко"),
              ("sometimes", "Не частіше ніж іноді"), ("often", "Гості можуть бути часто")]
    SMOKING = [("any", "Неважливо"), ("no_inside", "Не курить у приміщенні"), ("no_smokers", "Взагалі не курить")]
    PETS = [("any", "Неважливо"), ("no_pets", "Без домашніх тварин")]
    CHORES = [("any", "Неважливо"), ("split", "Рівний розподіл обов’язків"), ("flexible", "Гнучко, за домовленістю")]

    search_id = models.AutoField(primary_key=True)
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="search")
    city = models.CharField("Місто", max_length=100, blank=True)
    district = models.CharField("Бажаний район", max_length=100, blank=True)
    budget_min = models.PositiveIntegerField("Бюджет від, грн/міс.", null=True, blank=True)
    budget_max = models.PositiveIntegerField("Бюджет до, грн/міс.", null=True, blank=True)
    move_in_date = models.DateField("Бажана дата заселення", null=True, blank=True)
    req_age_min = models.PositiveSmallIntegerField("Вік від", null=True, blank=True, validators=[MinValueValidator(18), MaxValueValidator(120)])
    req_age_max = models.PositiveSmallIntegerField("Вік до", null=True, blank=True, validators=[MinValueValidator(18), MaxValueValidator(120)])
    req_sleep = models.CharField("Режим сну співмешканця", max_length=10, choices=SLEEP, default="any")
    req_min_cleanliness = models.PositiveSmallIntegerField("Мінімально прийнятна охайність", null=True, blank=True,
                                                          validators=SCALE_1_5)
    req_max_noise = models.PositiveSmallIntegerField("Максимально прийнятний шум", null=True, blank=True,
                                                    validators=SCALE_1_5)
    req_guests = models.CharField("Гості в оселі", max_length=10, choices=GUESTS, default="any")
    req_smoking = models.CharField("Куріння", max_length=12, choices=SMOKING, default="any")
    req_pets = models.CharField("Домашні тварини", max_length=10, choices=PETS, default="any")
    req_chores = models.CharField("Побутові обов’язки", max_length=10, choices=CHORES, default="any")

    class Meta:
        verbose_name = "параметри пошуку"
        verbose_name_plural = "параметри пошуку"

    def clean(self):
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValidationError("Мінімальний бюджет не може бути більшим за максимальний.")

    def __str__(self):
        return f"Пошук: {self.profile}"


class CriterionWeight(models.Model):
    """Важливість критерію (1–5) для користувача та ознака критичної вимоги."""

    weight_id = models.AutoField(primary_key=True)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="weights")
    criterion = models.CharField("Критерій", max_length=20, choices=CRITERIA)
    weight = models.PositiveSmallIntegerField("Важливість", default=3, validators=SCALE_1_5)
    is_critical = models.BooleanField("Критична вимога", default=False)

    class Meta:
        verbose_name = "важливість критерію"
        verbose_name_plural = "важливість критеріїв"
        constraints = [models.UniqueConstraint(fields=["profile", "criterion"], name="uniq_profile_criterion")]

    def __str__(self):
        return f"{self.profile}: {self.criterion}={self.weight}"
