from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.profile_view, name="view"),
    path("profile/edit/", views.profile_edit, name="edit"),
    path("lifestyle/", views.lifestyle_edit, name="lifestyle"),
    path("search/", views.search_edit, name="search"),
]
