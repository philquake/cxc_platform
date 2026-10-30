from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    ThrottledPasswordResetView, account, confirm_email_change, login_view, logout_view, resend_verification, signup,
    verify_email, verify_email_sent,
)

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup, name="signup"),
    path("verify/sent/", verify_email_sent, name="verify-email-sent"),
    path("verify/resend/", resend_verification, name="verify-email-resend"),
    path("verify/<uidb64>/<token>/", verify_email, name="verify-email"),
    path("email/confirm/<token>/", confirm_email_change, name="confirm-email-change"),
    path("profile/", account, name="account"),
    path(
        "password-reset/",
        ThrottledPasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change_form.html",
            success_url=reverse_lazy("password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("logout/", logout_view, name="logout"),
]