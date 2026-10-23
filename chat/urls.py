from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.conversation_list, name="list"),
    path("<int:conversation_id>/", views.conversation_detail, name="detail"),
    path("<int:conversation_id>/messages/", views.messages_api, name="messages"),
    path("<int:conversation_id>/send/", views.send_api, name="send"),
]
