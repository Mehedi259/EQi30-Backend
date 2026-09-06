import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import EmailVerificationOTP, PasswordResetOTP
from .serializers import (
    ChangePasswordSerializer,
    EmailVerifyOTPSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def _blacklist_all_tokens(user):
    """Invalidate every outstanding refresh token of the user."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def _send_otp_email(user, otp):
    try:
        send_mail(
            subject="Your EQi30 password reset code",
            message=(
                f"Your EQi30 password reset code is {otp.code}. "
                f"It expires in {settings.PASSWORD_RESET_OTP_TTL_MINUTES} minutes."
            ),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
        )
    except Exception:  # pragma: no cover - SMTP issues must not leak user existence
        logger.exception("Failed to send OTP email to %s", user.email)


def _send_email_verification_otp(user, otp):
    try:
        send_mail(
            subject="Verify your EQi30 email address",
            message=(
                f"Welcome to EQi30!\n\n"
                f"Your email verification code is {otp.code}. "
                f"It expires in {settings.PASSWORD_RESET_OTP_TTL_MINUTES} minutes.\n\n"
                f"Please enter this code to activate your account."
            ),
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to send email-verification OTP to %s", user.email)


class RegisterView(generics.CreateAPIView):
    """Create a pending (inactive) account and send an email-verification OTP.

    The user cannot log in until they submit the OTP to /auth/verify-email/.
    """

    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()  # created with is_active=False
        otp = EmailVerificationOTP.issue(user)
        _send_email_verification_otp(user, otp)
        return Response(
            {
                "detail": "Registration successful. Please check your email for a verification code.",
                "email": user.email,
                "onboarding_claimed": serializer.context.get("onboarding_claimed", False),
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    """Submit the email-verification OTP to activate the account.

    On success the user is activated and JWT tokens are returned so the client
    can proceed directly to the main app without a separate login step.
    """

    permission_classes = [AllowAny]

    @extend_schema(request=EmailVerifyOTPSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = EmailVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data["otp_obj"]
        user = otp.user

        # Activate the account and clean up the one-time code in one transaction.
        from django.db import transaction
        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=["is_active"])
            otp.delete()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "detail": "Email verified. Account activated.",
                "user": UserSerializer(user).data,
                "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
            },
            status=status.HTTP_200_OK,
        )


class ResendEmailOTPView(APIView):
    """Resend the email-verification OTP for a pending (inactive) account."""

    permission_classes = [AllowAny]

    @extend_schema(request=ForgotPasswordSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"].strip(),
            is_active=False,
        ).first()
        if user:
            otp = EmailVerificationOTP.issue(user)
            _send_email_verification_otp(user, otp)
        # Neutral response so the endpoint cannot probe which emails exist.
        return Response(
            {"detail": "If a pending account exists for that email, a new code has been sent."}
        )


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(
                {"refresh": ["Invalid or expired token."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Logged out."})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=ForgotPasswordSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"].strip()
        ).first()
        if user:
            _send_otp_email(user, PasswordResetOTP.issue(user))
        # Same response either way so the endpoint can't be used to probe emails.
        return Response({"detail": "If the email exists, an OTP has been sent."})


class ResendOTPView(ForgotPasswordView):
    """Issuing a new OTP invalidates the previous one (single active code)."""


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=VerifyOTPSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data["otp_obj"]
        otp.is_verified = True
        otp.save(update_fields=["is_verified"])
        return Response({"detail": "OTP verified."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=ResetPasswordSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data["otp_obj"]
        user = otp.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        # Codes are single-use and never stored permanently.
        PasswordResetOTP.objects.filter(user=user).delete()
        _blacklist_all_tokens(user)
        return Response({"detail": "Password has been reset. Please log in."})


class ChangePasswordView(APIView):
    @extend_schema(request=ChangePasswordSerializer, responses={200: OpenApiTypes.OBJECT})
    def put(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password changed."})


class DeleteAccountView(APIView):
    @extend_schema(request=None, responses={204: None})
    def delete(self, request):
        user = request.user
        _blacklist_all_tokens(user)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
