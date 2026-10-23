from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from interactions.models import ContactRequest, is_blocked_between

from .forms import ListingFilterForm, ListingForm
from .models import HousingListing, HousingPhoto


def _public_listings():
    return HousingListing.objects.filter(is_active=True, is_hidden=False, owner__is_active=True)


def _can_see_address(user, listing):
    """Точну адресу бачить власник і той, із ким власник має прийнятий запит (в будь-який бік).

    Для блокування в будь-який бік адреса не розкривається."""
    if listing.owner_id == user.pk:
        return True
    if is_blocked_between(user, listing.owner):
        return False
    return ContactRequest.objects.filter(status=ContactRequest.Status.ACCEPTED).filter(
        Q(sender=user, receiver=listing.owner) | Q(sender=listing.owner, receiver=user)).exists()


@login_required
def listing_list(request):
    form = ListingFilterForm(request.GET or None)
    listings = _public_listings().select_related("owner__profile").prefetch_related("photos")
    if form.is_valid():
        data = form.cleaned_data
        if data["city"]:
            listings = listings.filter(city__icontains=data["city"])
        if data["district"]:
            listings = listings.filter(district__icontains=data["district"])
        if data["max_price"]:
            listings = listings.filter(price_per_person__lte=data["max_price"])
        listings = listings.order_by({"cheap": "price_per_person", "expensive": "-price_per_person"}.get(data["sort"], "-created_at"))
    page = Paginator(listings, 9).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "housing/list.html", {"form": form, "page": page, "query": query.urlencode()})


@login_required
def my_listings(request):
    listings = HousingListing.objects.filter(owner=request.user).prefetch_related("photos")
    return render(request, "housing/mine.html", {"listings": listings})


@login_required
def listing_detail(request, housing_id):
    listing = get_object_or_404(HousingListing.objects.select_related("owner__profile").prefetch_related("photos"), pk=housing_id)
    is_owner = listing.owner_id == request.user.pk
    if not listing.is_public and not is_owner:
        return render(request, "404.html", status=404)
    existing = ContactRequest.objects.filter(
        sender=request.user, receiver=listing.owner, housing=listing,
        status__in=[ContactRequest.Status.PENDING, ContactRequest.Status.ACCEPTED]).first()
    return render(request, "housing/detail.html", {
        "listing": listing, "is_owner": is_owner, "show_address": _can_see_address(request.user, listing),
        "existing_request": existing})


@login_required
def listing_create(request):
    form = ListingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.owner = request.user
        listing.save()
        for image in form.cleaned_data["photos"]:
            HousingPhoto.objects.create(listing=listing, image=image)
        messages.success(request, "Оголошення опубліковано.")
        return redirect("housing:detail", housing_id=listing.pk)
    return render(request, "housing/form.html", {"form": form, "title": "Нове оголошення"})


@login_required
def listing_edit(request, housing_id):
    listing = get_object_or_404(HousingListing, pk=housing_id, owner=request.user)
    form = ListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        form.save()
        for image in form.cleaned_data["photos"]:
            HousingPhoto.objects.create(listing=listing, image=image)
        messages.success(request, "Зміни збережено.")
        return redirect("housing:detail", housing_id=listing.pk)
    return render(request, "housing/form.html", {"form": form, "title": "Редагування оголошення", "listing": listing})


@login_required
@require_POST
def listing_toggle(request, housing_id):
    listing = get_object_or_404(HousingListing, pk=housing_id, owner=request.user)
    listing.is_active = not listing.is_active
    listing.save(update_fields=["is_active"])
    messages.success(request, "Оголошення активовано." if listing.is_active else "Оголошення деактивовано і приховано з пошуку.")
    return redirect("housing:mine")


@login_required
def listing_delete(request, housing_id):
    listing = get_object_or_404(HousingListing, pk=housing_id, owner=request.user)
    if request.method == "POST":
        listing.delete()
        messages.success(request, "Оголошення видалено.")
        return redirect("housing:mine")
    return render(request, "housing/confirm_delete.html", {"listing": listing})


@login_required
@require_POST
def photo_delete(request, photo_id):
    photo = get_object_or_404(HousingPhoto, pk=photo_id, listing__owner=request.user)
    listing_id = photo.listing_id
    photo.image.delete(save=False)
    photo.delete()
    messages.success(request, "Фото видалено.")
    return redirect("housing:edit", housing_id=listing_id)
