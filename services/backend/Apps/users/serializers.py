from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import EmailVerificationOTP, PasswordResetOTP

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="profile.full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=30)
    session_uuid = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True,
        help_text="Anonymous onboarding session to attach to the new account.",
    )

    class Meta:
        model = User
        fields = ["email", "password", "full_name", "phone", "session_uuid"]

    def create(self, validated_data):
        from Apps.journey.services import claim_onboarding_session

        full_name = validated_data.pop("full_name", "")
        phone = validated_data.pop("phone", "")
        session_uuid = validated_data.pop("session_uuid", None)

        # The whole registration (user + profile + onboarding claim) is atomic.
        # The user is created with is_active=False (set by UserManager.create_user)
        # and is only activated after email OTP verification.
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)
            profile = user.profile  # created by the profiles post_save signal
            profile.full_name = full_name
            profile.phone = phone
            profile.save(update_fields=["full_name", "phone"])
            self.context["onboarding_claimed"] = (
                claim_onboarding_session(session_uuid, user) if session_uuid else False
            )
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Email + password login returning the token pair plus the user payload."""

    def validate(self, attrs):
        data = super().validate(attrs)
        return {
            "user": UserSerializer(self.user).data,
            "tokens": {"refresh": data["refresh"], "access": data["access"]},
        }


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerifyOTPSerializer(serializers.Serializer):
    """Validates the 6-digit code sent to the user during registration."""

    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        try:
            otp_obj = EmailVerificationOTP.objects.select_related("user").get(
                user__email__iexact=attrs["email"].strip(),
                code=attrs["otp"],
            )
        except EmailVerificationOTP.DoesNotExist:
            raise serializers.ValidationError({"otp": "Invalid or expired OTP."})
        if otp_obj.is_expired:
            raise serializers.ValidationError({"otp": "Invalid or expired OTP."})
        attrs["otp_obj"] = otp_obj
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        otp = (
            PasswordResetOTP.objects.filter(
                user__email__iexact=attrs["email"].strip(),
                code=attrs["otp"],
                is_used=False,
            )
            .select_related("user")
            .first()
        )
        if otp is None or otp.is_expired:
            raise serializers.ValidationError({"otp": "Invalid or expired OTP."})
        attrs["otp_obj"] = otp
        return attrs


class ResetPasswordSerializer(VerifyOTPSerializer):
    new_password = serializers.CharField(validators=[validate_password])

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs["otp_obj"].is_verified:
            raise serializers.ValidationError(
                {"otp": "OTP has not been verified. Call verify-otp first."}
            )
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
