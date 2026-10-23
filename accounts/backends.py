from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Стандартний бекенд, але з коректним повідомленням для деактивованих акаунтів.

    Звичайний ModelBackend не пускає неактивного користувача вже на етапі authenticate(),
    тому форма входу показувала «Невірна пошта або пароль» замість «Акаунт деактивовано».
    Тут authenticate() повертає користувача (лише при правильному паролі, тож існування акаунта
    не розкривається стороннім), а форма сама відмовляє через confirm_login_allowed().
    Активні сесії деактивованих користувачів, як і раніше, недійсні: get_user() їх не повертає.
    """

    def user_can_authenticate(self, user):
        return True

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            user = user_model._default_manager.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
        return user if user.is_active else None
