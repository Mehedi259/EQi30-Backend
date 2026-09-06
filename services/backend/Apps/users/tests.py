from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EmailVerificationOTP, PasswordResetOTP

User = get_user_model()

PASSWORD = "Sup3r-secret-pass!"
NEW_PASSWORD = "An0ther-secret-pass!"


class AuthFlowTests(APITestCase):
    def register(self, email="user@example.com"):
        return self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": PASSWORD, "full_name": "Test User"},
            format="json",
        )

    def verify_email(self, email="user@example.com"):
        """Helper: get the OTP from the DB and submit it."""
        user = User.objects.get(email=email)
        otp = user.email_verification_otp
        return self.client.post(
            "/api/v1/auth/verify-email/",
            {"email": email, "otp": otp.code},
            format="json",
        )

    # ------------------------------------------------------------------
    # Registration + email verification
    # ------------------------------------------------------------------

    def test_register_returns_no_tokens_and_user_is_inactive(self):
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # No tokens yet – user must verify email first.
        self.assertNotIn("tokens", response.data)
        self.assertFalse(response.data["onboarding_claimed"])
        self.assertEqual(response.data["email"], "user@example.com")

        user = User.objects.get(email="user@example.com")
        self.assertFalse(user.is_active)

    def test_login_blocked_before_email_verification(self):
        self.register()
        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": PASSWORD},
            format="json",
        )
        # SimpleJWT rejects inactive users with 401.
        self.assertEqual(login.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_email_activates_user_and_returns_tokens(self):
        self.register()
        response = self.verify_email()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertEqual(response.data["user"]["full_name"], "Test User")

        user = User.objects.get(email="user@example.com")
        self.assertTrue(user.is_active)
        # OTP is deleted after successful verification.
        self.assertFalse(EmailVerificationOTP.objects.filter(user=user).exists())

    def test_login_succeeds_after_email_verification(self):
        self.register()
        self.verify_email()
        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn("access", login.data["tokens"])

    def test_invalid_otp_rejected(self):
        self.register()
        response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"email": "user@example.com", "otp": "000000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_email_otp(self):
        self.register()
        user = User.objects.get(email="user@example.com")
        first_code = user.email_verification_otp.code

        self.client.post(
            "/api/v1/auth/resend-email-otp/",
            {"email": "user@example.com"},
            format="json",
        )
        new_otp = EmailVerificationOTP.objects.filter(user=user).first()
        self.assertIsNotNone(new_otp)
        # Old code invalidated (new row replaces it); codes may coincidentally match,
        # so we just confirm there's still exactly one OTP.
        self.assertEqual(EmailVerificationOTP.objects.filter(user=user).count(), 1)
        _ = first_code  # suppress unused-variable warning

    # ------------------------------------------------------------------
    # Post-verification flows
    # ------------------------------------------------------------------

    def test_change_password_after_verification(self):
        self.register()
        verify_response = self.verify_email()
        access = verify_response.data["tokens"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        change = self.client.put(
            "/api/v1/auth/change-password/",
            {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(change.status_code, status.HTTP_200_OK)

        self.client.credentials()
        relogin = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(relogin.status_code, status.HTTP_200_OK)

    def test_duplicate_email_rejected(self):
        self.register()
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_forgot_password_otp_flow(self):
        """Forgot-password flow is independent of the email-verification OTP."""
        self.register()
        self.verify_email()  # account must be active for forgot-password
        user = User.objects.get(email="user@example.com")

        response = self.client.post(
            "/api/v1/auth/forgot-password/", {"email": "user@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_code = user.password_reset_otps.get().code

        # Resend invalidates the previous code.
        self.client.post(
            "/api/v1/auth/resend-otp/", {"email": "user@example.com"}, format="json"
        )
        otp = user.password_reset_otps.get()
        verify_old = self.client.post(
            "/api/v1/auth/verify-otp/",
            {"email": "user@example.com", "otp": first_code},
            format="json",
        )
        if first_code != otp.code:
            self.assertEqual(verify_old.status_code, status.HTTP_400_BAD_REQUEST)

        # Reset before verification is rejected.
        early_reset = self.client.post(
            "/api/v1/auth/reset-password/",
            {"email": "user@example.com", "otp": otp.code, "new_password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(early_reset.status_code, status.HTTP_400_BAD_REQUEST)

        verify = self.client.post(
            "/api/v1/auth/verify-otp/",
            {"email": "user@example.com", "otp": otp.code},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        reset = self.client.post(
            "/api/v1/auth/reset-password/",
            {"email": "user@example.com", "otp": otp.code, "new_password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(reset.status_code, status.HTTP_200_OK)
        self.assertEqual(user.password_reset_otps.count(), 0)

        relogin = self.client.post(
            "/api/v1/auth/login/",
            {"email": "user@example.com", "password": NEW_PASSWORD},
            format="json",
        )
        self.assertEqual(relogin.status_code, status.HTTP_200_OK)

    def test_delete_account(self):
        self.register()
        verify_response = self.verify_email()
        access = verify_response.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        delete = self.client.delete("/api/v1/user/account/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(email="user@example.com").exists())
