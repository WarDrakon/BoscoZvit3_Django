import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from interactions.models import UserBlock, is_blocked_between

from .models import Conversation, Message

MAX_LENGTH = 2000


def _my_conversation(user, conversation_id):
    """Єдине місце перевірки прав: чужа розмова віддає 404, навіть якщо підставити її ID в URL."""
    return get_object_or_404(Conversation.objects.for_user(user).select_related(
        "user_one__profile", "user_two__profile"), pk=conversation_id)


def _serialize(message, me):
    local = timezone.localtime(message.created_at)
    return {"id": message.pk, "text": message.text, "mine": message.sender_id == me.pk,
            "time": local.strftime("%H:%M"), "date": local.strftime("%d.%m.%Y"), "read": message.read_at is not None}


@login_required
def conversation_list(request):
    conversations = list(Conversation.objects.for_user(request.user).select_related("user_one__profile", "user_two__profile")
                         .annotate(unread=Count("messages", filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=request.user))))
    for conversation in conversations:
        conversation.other = conversation.other_user(request.user)
        conversation.last = conversation.messages.order_by("-message_id").first()
    conversations.sort(key=lambda c: c.last.created_at if c.last else c.created_at, reverse=True)
    return render(request, "chat/list.html", {"conversations": conversations})


@login_required
def conversation_detail(request, conversation_id):
    conversation = _my_conversation(request.user, conversation_id)
    other = conversation.other_user(request.user)
    return render(request, "chat/detail.html", {
        "conversation": conversation, "other": other, "blocked": is_blocked_between(request.user, other),
        "i_blocked": UserBlock.objects.filter(blocker=request.user, blocked=other).exists()})


@login_required
@require_GET
def messages_api(request, conversation_id):
    """Повертає нові повідомлення (id > after) і позначає отримані як прочитані."""
    conversation = _my_conversation(request.user, conversation_id)
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    conversation.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
    new_messages = conversation.messages.filter(message_id__gt=after).select_related("sender")[:200]
    read_ids = list(conversation.messages.filter(sender=request.user, read_at__isnull=False)
                    .order_by("-message_id").values_list("message_id", flat=True)[:100])
    other = conversation.other_user(request.user)
    return JsonResponse({"messages": [_serialize(m, request.user) for m in new_messages], "read_ids": read_ids,
                         "blocked": is_blocked_between(request.user, other)})


@login_required
@require_POST
def send_api(request, conversation_id):
    conversation = _my_conversation(request.user, conversation_id)
    if is_blocked_between(request.user, conversation.other_user(request.user)):
        return JsonResponse({"error": "Надсилання повідомлень неможливе: користувача заблоковано."}, status=403)
    try:
        text = json.loads(request.body).get("text", "")
    except (ValueError, AttributeError):
        text = request.POST.get("text", "")
    text = (text or "").strip()
    if not text:
        return JsonResponse({"error": "Повідомлення не може бути порожнім."}, status=400)
    if len(text) > MAX_LENGTH:
        return JsonResponse({"error": f"Повідомлення задовге (максимум {MAX_LENGTH} символів)."}, status=400)
    message = Message.objects.create(conversation=conversation, sender=request.user, text=text)
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=message.created_at)
    return JsonResponse({"message": _serialize(message, request.user)}, status=201)
