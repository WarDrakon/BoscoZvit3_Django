from django.contrib import messages
from django.contrib.auth import login, logout, password_validation, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (LoginView, PasswordChangeView, PasswordResetCompleteView,
                                       PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView)
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

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


@require_POST
@never_cache
def password_check(request):
    """Підказка для індикатора на сторінці реєстрації: ті самі валідатори, що й у формі. Нічого не зберігає."""
    from config.password_validators import registration_validators
    from .models import User
    password = request.POST.get("password", "")[:128]
    user = User(email=request.POST.get("email", "")[:254], first_name=request.POST.get("first_name", "")[:60],
                last_name=request.POST.get("last_name", "")[:60])
    codes, texts = [], []
    if password:
        try:
            password_validation.validate_password(password, user, password_validators=registration_validators())
        except ValidationError as error:
            for item in error.error_list:
                codes.append(item.code)
                texts.append(" ".join(item.messages))
    return JsonResponse({"ok": not codes, "codes": codes, "messages": texts})
