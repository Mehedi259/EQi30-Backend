from datetime import timedelta

from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AnonymousOnboardingSession, AssessmentResult

PASSWORD = "Sup3r-secret-pass!"

# Codes in seed order; the AI recommendation used in tests reverses nothing,
# while the custom order puts STRESS_MANAGEMENT first.
CODES = [
    "SELF_MANAGEMENT",
    "INTERPERSONAL_MANAGEMENT",
    "STRESS_MANAGEMENT",
    "SPIRIT_MANAGEMENT",
    "EXECUTIVE_FUNCTION",
    "DECISION_MAKING",
]
AI_PRIORITIES = {code: i + 1 for i, code in enumerate(CODES)}
CUSTOM_ORDER = [
    "STRESS_MANAGEMENT",
    "SELF_MANAGEMENT",
    "INTERPERSONAL_MANAGEMENT",
    "SPIRIT_MANAGEMENT",
    "EXECUTIVE_FUNCTION",
    "DECISION_MAKING",
]


class OnboardingToJourneyFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_eqi30", "--demo-content")

    def create_session(self):
        response = self.client.post("/api/v1/onboarding/session/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data["session_uuid"]

    def submit_assessment(self, session_uuid):
        payload = {
            "results": [
                {"competency": code, "score": 50 + i, "ai_priority": AI_PRIORITIES[code]}
                for i, code in enumerate(CODES)
            ]
        }
        return self.client.post(
            f"/api/v1/onboarding/{session_uuid}/assessment/", payload, format="json"
        )

    def test_full_flow_assessment_to_dashboard(self):
        session_uuid = self.create_session()

        # --- AI assessment ---
        response = self.submit_assessment(session_uuid)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["results"]), 6)

        # Duplicate priorities are rejected.
        bad = self.client.patch(
            f"/api/v1/onboarding/{session_uuid}/priorities/",
            {
                "journey_type": "CUSTOM",
                "priorities": [
                    {"competency": code, "priority": 1} for code in CODES
                ],
            },
            format="json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        # --- Custom priorities (ai_priority must survive untouched) ---
        response = self.client.patch(
            f"/api/v1/onboarding/{session_uuid}/priorities/",
            {
                "journey_type": "CUSTOM",
                "priorities": [
                    {"competency": code, "priority": i + 1}
                    for i, code in enumerate(CUSTOM_ORDER)
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for entry in response.data["results"]:
            self.assertEqual(entry["ai_priority"], AI_PRIORITIES[entry["competency"]])

        # --- Growth pace + practice time ---
        response = self.client.put(
            f"/api/v1/onboarding/{session_uuid}/growth-plan/",
            {"growth_plan": "MEDIUM"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.put(
            f"/api/v1/onboarding/{session_uuid}/practice-time/",
            {"practice_time": "MORNING"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # --- Registration claims the session; tokens come after email verification ---
        reg_response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "journey@example.com",
                "password": PASSWORD,
                "full_name": "Journey Tester",
                "session_uuid": session_uuid,
            },
            format="json",
        )
        self.assertEqual(reg_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(reg_response.data["onboarding_claimed"])

        # Verify email OTP to activate the account and receive tokens.
        from Apps.users.models import EmailVerificationOTP
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        _user = _User.objects.get(email="journey@example.com")
        email_otp = EmailVerificationOTP.objects.get(user=_user)
        verify_response = self.client.post(
            "/api/v1/auth/verify-email/",
            {"email": "journey@example.com", "otp": email_otp.code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        access = verify_response.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        session = AnonymousOnboardingSession.objects.get(session_uuid=session_uuid)
        self.assertEqual(session.status, AnonymousOnboardingSession.Status.CLAIMED)
        self.assertEqual(AssessmentResult.objects.filter(session=session).count(), 0)
        self.assertEqual(
            AssessmentResult.objects.filter(user__email="journey@example.com").count(), 6
        )

        # --- Personalized journey follows the custom order ---
        response = self.client.get("/api/v1/journey/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["journey"]["journey_type"], "CUSTOM")
        section_codes = [s["competency"]["code"] for s in response.data["sections"]]
        self.assertEqual(section_codes, CUSTOM_ORDER)
        self.assertTrue(all(len(s["abilities"]) == 5 for s in response.data["sections"]))

        # --- Today: MEDIUM pace → 2 sessions on day 1, from priority-1 competency ---
        response = self.client.get("/api/v1/journey/today/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["journey"]["current_day"], 1)
        self.assertEqual(len(response.data["sessions"]), 2)
        self.assertEqual(
            {s["competency"]["code"] for s in response.data["sessions"]},
            {"STRESS_MANAGEMENT"},
        )
        self.assertTrue(all(s["has_content"] for s in response.data["sessions"]))
        first = response.data["sessions"][0]

        # --- Learning content is served from the backend ---
        response = self.client.get(
            f"/api/v1/abilities/{first['ability']['id']}/days/{first['content_day']}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("teaching_content", response.data)

        # --- Completing a session updates progress and awards First Step ---
        response = self.client.post(f"/api/v1/sessions/{first['session_id']}/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["session"]["status"], "COMPLETED")
        self.assertIn("First Step", [b["name"] for b in response.data["new_badges"]])

        # Completing again is idempotent (no duplicate badges).
        response = self.client.post(f"/api/v1/sessions/{first['session_id']}/complete/")
        self.assertEqual(response.data["new_badges"], [])

        # --- Reflection ---
        response = self.client.post(
            f"/api/v1/sessions/{first['session_id']}/reflection/",
            {"response": "Calmer", "reflection_text": "Felt easier than expected."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # --- Weekly check-in ---
        response = self.client.post(
            "/api/v1/check-ins/weekly/",
            {"week_number": 1, "answers": {"mood": "good"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # --- Dashboard + tracker reflect real completion records ---
        response = self.client.get("/api/v1/home/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["name"], "Journey Tester")
        self.assertEqual(response.data["completed_activities"], 1)
        self.assertEqual(response.data["streak_days"], 1)
        self.assertEqual(response.data["today"]["sessions_remaining"], 1)

        response = self.client.get("/api/v1/progress/tracker/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall"]["completed_abilities"], 1)
        self.assertEqual(response.data["competencies"][0]["competency"]["code"], "STRESS_MANAGEMENT")
        self.assertEqual(response.data["competencies"][0]["completed_abilities"], 1)
        self.assertEqual(len(response.data["badges"]["earned"]), 1)

        # --- History ---
        response = self.client.get("/api/v1/journey/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["status"], "IN_PROGRESS")

    def test_expired_session_returns_410_and_data_is_deleted(self):
        session_uuid = self.create_session()
        self.submit_assessment(session_uuid)
        AnonymousOnboardingSession.objects.filter(session_uuid=session_uuid).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.submit_assessment(session_uuid)
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertFalse(
            AnonymousOnboardingSession.objects.filter(session_uuid=session_uuid).exists()
        )
        self.assertEqual(AssessmentResult.objects.count(), 0)

    def test_expired_session_claim_fails_but_registration_succeeds(self):
        session_uuid = self.create_session()
        self.submit_assessment(session_uuid)
        AnonymousOnboardingSession.objects.filter(session_uuid=session_uuid).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.post(
            "/api/v1/auth/register/",
            {"email": "late@example.com", "password": PASSWORD, "session_uuid": session_uuid},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["onboarding_claimed"])

    def test_assessment_requires_all_competencies(self):
        session_uuid = self.create_session()
        response = self.client.post(
            f"/api/v1/onboarding/{session_uuid}/assessment/",
            {"results": [{"competency": "SELF_MANAGEMENT", "score": 50, "ai_priority": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
