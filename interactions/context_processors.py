def badges(request):
    """Лічильники для навігації: нові запити та непрочитані повідомлення."""
    user = request.user
    if not user.is_authenticated:
        return {}
    from chat.models import Message
    from .models import ContactRequest

    return {
        "nav_pending_requests": ContactRequest.objects.filter(receiver=user, status=ContactRequest.Status.PENDING).count(),
        "nav_unread_messages": Message.objects.filter(
            conversation__in=_my_conversations(user), read_at__isnull=True).exclude(sender=user).count(),
    }


def _my_conversations(user):
    from chat.models import Conversation
    return Conversation.objects.for_user(user)
