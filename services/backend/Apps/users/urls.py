from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/verify-email/", views.VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/resend-email-otp/", views.ResendEmailOTPView.as_view(), name="auth-resend-email-otp"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/forgot-password/", views.ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/verify-otp/", views.VerifyOTPView.as_view(), name="auth-verify-otp"),
    path("auth/resend-otp/", views.ResendOTPView.as_view(), name="auth-resend-otp"),
    path("auth/reset-password/", views.ResetPasswordView.as_view(), name="auth-reset-password"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="auth-change-password"),
    path("user/account/", views.DeleteAccountView.as_view(), name="user-account"),
]
