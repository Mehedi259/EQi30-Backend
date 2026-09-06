import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Manager for the email-login user model (no username field)."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        # New users must verify their email before they can log in.
        extra_fields.setdefault("is_active", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """EQi30 account. Email is the login identifier; names live on UserProfile."""

    username = None
    first_name = None
    last_name = None
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class PasswordResetOTP(models.Model):
    """Short-lived 6-digit code for the forgot-password flow.

    Codes are single-use: issuing a new code (resend) deletes previous ones,
    and every code for the user is deleted once the password reset succeeds,
    so codes are never stored permanently.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_otps",
    )
    code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "password reset OTP"

    def __str__(self):
        return f"OTP for {self.user} (expires {self.expires_at:%Y-%m-%d %H:%M})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @classmethod
    def issue(cls, user):
        """Invalidate any previous codes and create a fresh one."""
        cls.objects.filter(user=user).delete()
        return cls.objects.create(
            user=user,
            code=f"{secrets.randbelow(10**6):06d}",
            expires_at=timezone.now()
            + timedelta(minutes=settings.PASSWORD_RESET_OTP_TTL_MINUTES),
        )


class EmailVerificationOTP(models.Model):
    """Short-lived 6-digit code sent after registration to verify the user's email.

    The account remains inactive (is_active=False) until this code is
    successfully submitted. Once verified the OTP row is deleted.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_otp",
    )
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "email verification OTP"

    def __str__(self):
        return f"Email-OTP for {self.user} (expires {self.expires_at:%Y-%m-%d %H:%M})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @classmethod
    def issue(cls, user):
        """Invalidate any previous code and create a fresh one."""
        cls.objects.filter(user=user).delete()
        return cls.objects.create(
            user=user,
            code=f"{secrets.randbelow(10**6):06d}",
            expires_at=timezone.now()
            + timedelta(minutes=settings.PASSWORD_RESET_OTP_TTL_MINUTES),
        )
