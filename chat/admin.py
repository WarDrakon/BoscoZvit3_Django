from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("conversation_id", "user_one", "user_two", "created_at", "updated_at")
    search_fields = ("user_one__email", "user_two__email")
    list_filter = ("created_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("message_id", "conversation", "sender", "created_at", "read_at")
    search_fields = ("text", "sender__email")
    list_filter = ("created_at",)
