from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.SiteLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.account_settings, name="settings"),
    path("password-check/", views.password_check, name="password_check"),
    path("password/", views.SitePasswordChangeView.as_view(), name="password_change"),
    path("deactivate/", views.deactivate_account, name="deactivate"),
    path("delete/", views.delete_account, name="delete"),
    path("password-reset/", views.SitePasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.SitePasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", views.SitePasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", views.SitePasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
