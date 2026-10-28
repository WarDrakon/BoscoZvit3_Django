from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from config.validators import validate_image_file


class HousingListing(models.Model):
    housing_id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="housing_listings")
    title = models.CharField("Заголовок", max_length=140)
    city = models.CharField("Місто", max_length=100)
    district = models.CharField("Район", max_length=100, blank=True)
    address = models.CharField("Точна адреса (приховано від публіки)", max_length=200, blank=True)
    price_per_person = models.PositiveIntegerField("Вартість на одну людину, грн/міс.",
                                                   validators=[MinValueValidator(1), MaxValueValidator(1_000_000)])
    rooms = models.PositiveSmallIntegerField("Кількість кімнат", default=1,
                                             validators=[MinValueValidator(1), MaxValueValidator(20)])
    free_places = models.PositiveSmallIntegerField("Вільних місць", default=1,
                                                   validators=[MinValueValidator(1), MaxValueValidator(20)])
    description = models.TextField("Опис умов проживання", max_length=3000)
    is_active = models.BooleanField("Оголошення активне", default=True)
    is_hidden = models.BooleanField("Приховано модератором", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "оголошення про житло"
        verbose_name_plural = "оголошення про житло"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["city", "district"]), models.Index(fields=["is_active", "is_hidden"])]

    def __str__(self):
        return f"{self.title} ({self.city})"

    def get_absolute_url(self):
        return reverse("housing:detail", kwargs={"housing_id": self.pk})

    @property
    def is_public(self):
        return self.is_active and not self.is_hidden


class HousingPhoto(models.Model):
    photo_id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(HousingListing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField("Фото", upload_to="housing/", validators=[validate_image_file])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "фото житла"
        verbose_name_plural = "фото житла"
        ordering = ["photo_id"]

    def __str__(self):
        return f"Фото #{self.photo_id} до {self.listing_id}"
