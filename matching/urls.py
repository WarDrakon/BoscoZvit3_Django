from django.urls import path

from . import views

app_name = "matching"

urlpatterns = [
    path("", views.recommendations, name="recommendations"),
    path("<int:profile_id>/", views.candidate_detail, name="candidate"),
]
