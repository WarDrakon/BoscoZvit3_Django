from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm

from config.forms import StyledFormMixin

from .models import User


class RegisterForm(StyledFormMixin, forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                help_text="Щонайменше 8 символів, не лише цифри.")
    password2 = forms.CharField(label="Підтвердіть пароль", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {"email": forms.EmailInput(attrs={"autocomplete": "email"})}

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
                                                               last_name=cleaned.get("last_name", "")))
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
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


class AccountForm(StyledFormMixin, forms.ModelForm):
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
