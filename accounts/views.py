from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (LoginView, PasswordChangeView, PasswordResetCompleteView,
                                       PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import (AccountForm, ConfirmPasswordForm, EmailLoginForm, RegisterForm, StyledPasswordChangeForm,
                    StyledPasswordResetForm, StyledSetPasswordForm)


def register(request):
    if request.user.is_authenticated:
        return redirect("profiles:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Акаунт створено. Заповніть профіль і анкету, щоб отримати рекомендації.")
        return redirect("profiles:dashboard")
    return render(request, "accounts/register.html", {"form": form})


class SiteLoginView(LoginView):
    authentication_form = EmailLoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    messages.info(request, "Ви вийшли з акаунта.")
    return redirect("home")


@login_required
def account_settings(request):
    form = AccountForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Особисті дані оновлено.")
        return redirect("accounts:settings")
    return render(request, "accounts/settings.html", {"form": form})


class SitePasswordChangeView(PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:settings")

    def form_valid(self, form):
        messages.success(self.request, "Пароль змінено.")
        return super().form_valid(form)


@login_required
@require_http_methods(["GET", "POST"])
def deactivate_account(request):
    form = ConfirmPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        user.is_active = False
        user.save(update_fields=["is_active"])
        user.profile.is_active_search = False
        user.profile.save(update_fields=["is_active_search"])
        logout(request)
        messages.info(request, "Акаунт деактивовано. Ваш профіль більше не показується в пошуку.")
        return redirect("home")
    return render(request, "accounts/deactivate.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def delete_account(request):
    form = ConfirmPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        logout(request)
        user.delete()  # каскадно видаляє профіль, анкети, оголошення, запити та повідомлення
        messages.info(request, "Акаунт і всі пов’язані дані видалено.")
        return redirect("home")
    return render(request, "accounts/delete.html", {"form": form})


class SitePasswordResetView(PasswordResetView):
    form_class = StyledPasswordResetForm
    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class SitePasswordResetDoneView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class SitePasswordResetConfirmView(PasswordResetConfirmView):
    form_class = StyledSetPasswordForm
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class SitePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"
