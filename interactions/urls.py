from django.urls import path

from . import views

app_name = "interactions"

urlpatterns = [
    path("", views.request_list, name="list"),
    path("send/<int:user_id>/", views.send_request, name="send"),
    path("<int:request_id>/cancel/", views.cancel_request, name="cancel"),
    path("<int:request_id>/<slug:action>/", views.respond_request, name="respond"),
    path("blocks/", views.block_list, name="blocks"),
    path("block/<int:user_id>/", views.block_user, name="block"),
    path("unblock/<int:user_id>/", views.unblock_user, name="unblock"),
    path("report/user/<int:user_id>/", views.report_user, name="report_user"),
    path("report/listing/<int:housing_id>/", views.report_listing, name="report_listing"),
]
