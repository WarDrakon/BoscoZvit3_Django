from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm

from config.forms import LiveValidationMixin, StyledFormMixin
from config.person_validators import AGE_MAX, AGE_MIN
from config.password_validators import registration_validators

from .models import User


class RegisterForm(LiveValidationMixin, StyledFormMixin, forms.ModelForm):
    live_names = {"first_name": "Ім’я", "last_name": "Прізвище"}

    # data-pw-*: підключають індикатор надійності (static/js/password.js). Це лише підказка в браузері,
    # остаточну перевірку виконують валідатори Django у clean() нижче.
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-pw": "main"}),
                                help_text="Щонайменше 8 символів: великі й малі літери, цифри та спеціальні символи.")
    password2 = forms.CharField(label="Підтвердіть пароль", widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-pw": "confirm"}))
    birth_date = forms.DateField(label="Дата народження", required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                 help_text=f"Вік має бути від {AGE_MIN} до {AGE_MAX} років. Іншим користувачам показується лише вік.")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {"email": forms.EmailInput(attrs={"autocomplete": "email"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password2"].widget.attrs["data-pw-main"] = self["password1"].id_for_label

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Користувач із такою поштою вже зареєстрований.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Паролі не збігаються.")
        elif p1:
            try:
                password_validation.validate_password(p1, User(email=cleaned.get("email", ""),
                                                               first_name=cleaned.get("first_name", ""),
                                                               last_name=cleaned.get("last_name", "")),
                                                      password_validators=registration_validators())
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            birth_date = self.cleaned_data.get("birth_date")
            if birth_date:
                profile = user.profile
                profile.birth_date = birth_date
                profile.save(update_fields=["birth_date"])
        return user


class EmailLoginForm(StyledFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Невірна пошта або пароль. Перевірте дані та спробуйте ще раз.",
        "inactive": "Цей акаунт деактивовано. Зверніться до адміністратора, щоб його відновити.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Електронна пошта"
        self.fields["username"].widget = forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email", "class": "input"})
        self.fields["password"].label = "Пароль"


class AccountForm(LiveValidationMixin, StyledFormMixin, forms.ModelForm):
    live_names = {"first_name": "Ім’я", "last_name": "Прізвище"}

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ця пошта вже використовується іншим акаунтом.")
        return email


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class StyledPasswordResetForm(StyledFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass


class ConfirmPasswordForm(StyledFormMixin, forms.Form):
    """Підтвердження пароля перед небезпечною дією (деактивація / видалення)."""

    password = forms.CharField(label="Ваш пароль", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Пароль невірний.")
        return password
