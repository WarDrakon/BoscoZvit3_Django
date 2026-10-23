from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from chat.models import Conversation
from housing.models import HousingListing

from .forms import ContactRequestForm, ReportForm
from .models import ContactRequest, Report, UserBlock, is_blocked_between

User = get_user_model()


def _active_user(user_id):
    return get_object_or_404(User, pk=user_id, is_active=True)


@login_required
def request_list(request):
    base = ContactRequest.objects.select_related("sender__profile", "receiver__profile", "housing")
    return render(request, "interactions/requests.html", {
        "incoming": base.filter(receiver=request.user).order_by("status", "-created_at"),
        "outgoing": base.filter(sender=request.user)})


@login_required
def send_request(request, user_id):
    receiver = _active_user(user_id)
    housing = None
    if request.GET.get("housing") or request.POST.get("housing"):
        housing = get_object_or_404(HousingListing, pk=request.GET.get("housing") or request.POST.get("housing"),
                                    owner=receiver, is_active=True, is_hidden=False)
    form = ContactRequestForm(request.POST or None)
    back = redirect("matching:candidate", profile_id=receiver.profile.pk)

    if receiver == request.user:
        messages.error(request, "Не можна надіслати запит самому собі.")
        return redirect("matching:recommendations")
    if is_blocked_between(request.user, receiver):
        messages.error(request, "Надіслати запит цьому користувачу неможливо.")
        return redirect("matching:recommendations")
    pair = ContactRequest.objects.filter(
        Q(sender=request.user, receiver=receiver) | Q(sender=receiver, receiver=request.user),
        status__in=[ContactRequest.Status.PENDING, ContactRequest.Status.ACCEPTED])
    if pair.exists():
        messages.info(request, "Між вами вже є активний або прийнятий запит. Перегляньте розділ «Запити».")
        return redirect("interactions:list")

    if request.method == "POST" and form.is_valid():
        ContactRequest.objects.create(sender=request.user, receiver=receiver, housing=housing,
                                      message=form.cleaned_data["message"])
        messages.success(request, f"Запит надіслано: {receiver.profile.display_name}. Ми повідомимо, коли він відповість.")
        return back
    return render(request, "interactions/send_request.html", {"form": form, "receiver": receiver, "housing": housing})


@login_required
@require_POST
def respond_request(request, request_id, action):
    contact = get_object_or_404(ContactRequest, pk=request_id, receiver=request.user, status=ContactRequest.Status.PENDING)
    if is_blocked_between(contact.sender, contact.receiver):
        messages.error(request, "Дія недоступна: користувача заблоковано.")
        return redirect("interactions:list")
    if action not in ("accept", "decline"):
        return redirect("interactions:list")
    if action == "accept":
        contact.status = ContactRequest.Status.ACCEPTED
        contact.responded_at = timezone.now()
        contact.save(update_fields=["status", "responded_at"])
        conversation = Conversation.objects.get_or_create_between(contact.sender, contact.receiver)
        messages.success(request, "Запит прийнято. Тепер ви можете листуватися.")
        return redirect("chat:detail", conversation_id=conversation.pk)
    contact.status = ContactRequest.Status.DECLINED
    contact.responded_at = timezone.now()
    contact.save(update_fields=["status", "responded_at"])
    messages.info(request, "Запит відхилено.")
    return redirect("interactions:list")


@login_required
@require_POST
def cancel_request(request, request_id):
    contact = get_object_or_404(ContactRequest, pk=request_id, sender=request.user, status=ContactRequest.Status.PENDING)
    contact.status = ContactRequest.Status.CANCELLED
    contact.responded_at = timezone.now()
    contact.save(update_fields=["status", "responded_at"])
    messages.info(request, "Запит скасовано.")
    return redirect("interactions:list")


@login_required
@require_POST
def block_user(request, user_id):
    target = _active_user(user_id)
    if target == request.user:
        messages.error(request, "Не можна заблокувати самого себе.")
        return redirect("interactions:blocks")
    UserBlock.objects.get_or_create(blocker=request.user, blocked=target)
    ContactRequest.objects.filter(
        Q(sender=request.user, receiver=target) | Q(sender=target, receiver=request.user),
        status=ContactRequest.Status.PENDING).update(status=ContactRequest.Status.CANCELLED, responded_at=timezone.now())
    messages.success(request, f"{target.profile.display_name} заблоковано. Переписка стала недоступною для нових повідомлень.")
    return redirect("interactions:blocks")


@login_required
@require_POST
def unblock_user(request, user_id):
    UserBlock.objects.filter(blocker=request.user, blocked_id=user_id).delete()
    messages.success(request, "Користувача розблоковано.")
    return redirect("interactions:blocks")


@login_required
def block_list(request):
    blocks = UserBlock.objects.filter(blocker=request.user).select_related("blocked__profile")
    return render(request, "interactions/blocks.html", {"blocks": blocks})


@login_required
def report_user(request, user_id):
    target = _active_user(user_id)
    return _report(request, reported_user=target, title=f"Скарга на користувача {target.profile.display_name}")


@login_required
def report_listing(request, housing_id):
    listing = get_object_or_404(HousingListing, pk=housing_id)
    return _report(request, housing=listing, reported_user=listing.owner, title=f"Скарга на оголошення «{listing.title}»")


def _report(request, title, reported_user=None, housing=None):
    if reported_user == request.user:
        messages.error(request, "Не можна поскаржитися на себе.")
        return redirect("profiles:dashboard")
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.reporter, report.reported_user, report.housing = request.user, reported_user, housing
        report.save()
        messages.success(request, "Скаргу надіслано модераторам. Дякуємо, що допомагаєте робити сервіс безпечнішим.")
        return redirect("profiles:dashboard")
    return render(request, "interactions/report.html", {"form": form, "title": title})
