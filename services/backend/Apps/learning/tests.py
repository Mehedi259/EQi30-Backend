from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from Apps.journey.models import UserJourney
from Apps.learning.models import DailyReflection, UserDailySession

User = get_user_model()


class WeeklyCheckInAndReflectionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_eqi30", "--demo-content")

    def setUp(self):
        self.user = User.objects.create_user(
            email="learner@example.com", password="StrongPassword123!", is_active=True
        )
        self.client.force_authenticate(user=self.user)

    def test_weekly_checkin_not_eligible_on_day_1_after_one_exercise(self):
        today_res = self.client.get("/api/v1/journey/today/")
        self.assertEqual(today_res.status_code, status.HTTP_200_OK)
        session_id = today_res.data["sessions"][0]["session_id"]

        complete_res = self.client.post(f"/api/v1/sessions/{session_id}/complete/")
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)

        weekly_res = self.client.get("/api/v1/check-ins/weekly/")
        self.assertEqual(weekly_res.status_code, status.HTTP_200_OK)
        self.assertFalse(weekly_res.data["eligible"])
        self.assertEqual(weekly_res.data["week_number"], 1)
        self.assertEqual(weekly_res.data["skills_count"], 1)

    def test_weekly_checkin_eligible_on_day_7_and_marks_submitted(self):
        self.client.get("/api/v1/journey/today/")
        journey = UserJourney.objects.get(user=self.user)
        from datetime import timedelta
        from django.utils import timezone

        journey.start_date = timezone.localdate() - timedelta(days=6)
        journey.current_day = 7
        journey.save(update_fields=["start_date", "current_day"])

        sess = UserDailySession.objects.filter(user=self.user, journey=journey).first()
        sess.day_number = 7
        sess.status = UserDailySession.Status.COMPLETED
        sess.save(update_fields=["day_number", "status"])

        before = self.client.get("/api/v1/check-ins/weekly/")
        self.assertTrue(before.data["eligible"])
        self.assertIn(sess.ability.name, before.data["skills_practiced"])

        post_res = self.client.post(
            "/api/v1/check-ins/weekly/",
            {"week_number": 1, "answers": {"practiced": "yes", "felt": "good"}},
            format="json",
        )
        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED)

        after = self.client.get("/api/v1/check-ins/weekly/")
        self.assertFalse(after.data["eligible"])
        self.assertTrue(after.data["already_submitted"])

    def test_partial_reflection_updates_preserve_earlier_fields(self):
        today_res = self.client.get("/api/v1/journey/today/")
        session_id = today_res.data["sessions"][0]["session_id"]

        res1 = self.client.post(
            f"/api/v1/sessions/{session_id}/reflection/",
            {"practice_answer": "Feeling hopeful today", "reflection_text": "Took a breath"},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        res2 = self.client.post(
            f"/api/v1/sessions/{session_id}/reflection/",
            {"response": "Calm"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)

        saved = DailyReflection.objects.get(session_id=session_id)
        self.assertEqual(saved.practice_answer, "Feeling hopeful today")
        self.assertEqual(saved.reflection_text, "Took a breath")
        self.assertEqual(saved.response, "Calm")
