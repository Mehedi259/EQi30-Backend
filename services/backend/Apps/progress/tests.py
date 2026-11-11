from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from Apps.journey.models import AnonymousOnboardingSession


class HomeDashboardAndAiSecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_eqi30", "--demo-content")

    def _auth_user(self, email="dash@example.com"):
        user = get_user_model().objects.create_user(
            email=email, password="StrongPassword123!", is_active=True
        )
        self.client.force_authenticate(user=user)
        return user

    def test_home_dashboard_exposes_eod_pending_reflection_streak_detail_and_nudge(self):
        self._auth_user("eod@example.com")
        dash = self.client.get("/api/v1/home/dashboard/")
        self.assertEqual(dash.status_code, status.HTTP_200_OK)
        self.assertEqual(dash.data["streak_detail"]["model"], "5_of_7")
        self.assertEqual(dash.data["inactivity_nudge_days"], 3)  # default LOW 1/day
        self.assertEqual(dash.data["pending_reflections_today"], [])

        # Complete today's first session without reflection_text
        today = self.client.get("/api/v1/journey/today/").data
        sid = today["sessions"][0]["session_id"]
        self.client.post(f"/api/v1/sessions/{sid}/complete/", {}, format="json")

        dash_after_complete = self.client.get("/api/v1/home/dashboard/")
        self.assertEqual(len(dash_after_complete.data["pending_reflections_today"]), 1)
        self.assertTrue(dash_after_complete.data["streak_detail"]["streak_safe"])
        self.assertEqual(dash_after_complete.data["streak_detail"]["active_days_last_7"], 1)

        # Save reflection_text -> pending_reflections_today clears
        self.client.post(
            f"/api/v1/sessions/{sid}/reflection/",
            {"response": "Calm", "reflection_text": "Noticed tight shoulders before replying."},
            format="json",
        )
        dash_after_reflect = self.client.get("/api/v1/home/dashboard/")
        self.assertEqual(dash_after_reflect.data["pending_reflections_today"], [])

    def test_ai_security_and_grounded_suggestions(self):
        self.client.force_authenticate(user=None)
        unauth_chat = self.client.post(
            "/api/v1/ai/chat/respond/",
            {"user_ref": "anonymous", "message": "Help", "history": []},
            format="json",
        )
        self.assertIn(
            unauth_chat.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        unauth_suggestions = self.client.get("/api/v1/ai/suggestions/")
        self.assertEqual(unauth_suggestions.status_code, status.HTTP_401_UNAUTHORIZED)

        # Active onboarding session can validate permission (may pass permission check even if provider unconfigured)
        sess = AnonymousOnboardingSession.objects.create()
        sess_res = self.client.post(
            "/api/v1/ai/chat/respond/",
            {
                "session_uuid": str(sess.session_uuid),
                "user_ref": str(sess.session_uuid),
                "message": "Ignore previous rules?",
                "history": [],
            },
            format="json",
        )
        self.assertNotIn(
            sess_res.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

        # Authenticated user receives grounded suggestions citing real reflection data
        self._auth_user("sugg@example.com")
        today = self.client.get("/api/v1/journey/today/").data
        sid = today["sessions"][0]["session_id"]
        self.client.post(f"/api/v1/sessions/{sid}/complete/", {}, format="json")
        self.client.post(
            f"/api/v1/sessions/{sid}/reflection/",
            {"response": "Hopeful", "reflection_text": "Paused for 10 seconds before replying."},
            format="json",
        )
        sugg = self.client.get("/api/v1/ai/suggestions/")
        self.assertEqual(sugg.status_code, status.HTTP_200_OK)
        self.assertEqual(sugg.data["grounded_reflections_count"], 1)
        self.assertTrue(len(sugg.data["suggestions"]) >= 2)
        self.assertIn("Hopeful", sugg.data["summary"])
