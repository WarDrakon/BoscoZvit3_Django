from django.urls import path

from . import views

app_name = "housing"

urlpatterns = [
    path("", views.listing_list, name="list"),
    path("mine/", views.my_listings, name="mine"),
    path("new/", views.listing_create, name="create"),
    path("<int:housing_id>/", views.listing_detail, name="detail"),
    path("<int:housing_id>/edit/", views.listing_edit, name="edit"),
    path("<int:housing_id>/toggle/", views.listing_toggle, name="toggle"),
    path("<int:housing_id>/delete/", views.listing_delete, name="delete"),
    path("photos/<int:photo_id>/delete/", views.photo_delete, name="photo_delete"),
]
