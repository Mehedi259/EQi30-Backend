from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from Apps.journey import services as journey_services
from Apps.learning.models import UserDailySession

from . import services
from .models import Badge
from .serializers import BadgeSerializer, UserBadgeSerializer


class ProgressTrackerView(APIView):
    """Overall, competency and ability progress + streak, goals and badges."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        user = request.user
        journey = journey_services.get_active_journey(user)
        ordered = journey_services.ordered_competencies(user, journey)
        profile = getattr(user, "profile", None)

        earned = user.badges.select_related("badge")
        earned_ids = {ub.badge_id for ub in earned}
        return Response(
            {
                "overall": services.overall_progress(user),
                "competencies": services.competency_progress(user, ordered),
                "weekly_activity": services.weekly_activity(user),
                "streak_days": services.get_streak(user),
                "active_goal": {
                    "daily_goal_minutes": profile.daily_goal_minutes if profile else 5,
                    "minutes_completed_today": services.minutes_completed_today(user),
                },
                "badges": {
                    "earned": UserBadgeSerializer(earned, many=True).data,
                    "available": BadgeSerializer(
                        Badge.objects.filter(is_active=True).exclude(id__in=earned_ids),
                        many=True,
                    ).data,
                },
            }
        )


class HomeDashboardView(APIView):
    """Single aggregated endpoint for the Home screen."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        user = request.user
        profile = getattr(user, "profile", None)
        today_payload = journey_services.journey_today(user)
        sessions = today_payload.get("sessions", [])
        next_session = next(
            (s for s in sessions if s["status"] != UserDailySession.Status.COMPLETED),
            None,
        )
        return Response(
            {
                "user": {
                    "id": user.id,
                    "name": (profile.full_name if profile else "") or user.email.split("@")[0],
                    "email": user.email,
                    "profile_image": profile.profile_image.url
                    if profile and profile.profile_image
                    else None,
                },
                "date": timezone.localdate(),
                "journey": today_payload["journey"],
                "current_ability": (next_session or (sessions[-1] if sessions else None)),
                "overall_progress": services.overall_progress(user),
                "completed_activities": services._completed_sessions(user).count(),
                "streak_days": services.get_streak(user),
                "today": {
                    "sessions_total": len(sessions),
                    "sessions_remaining": today_payload.get("sessions_remaining", 0),
                    "estimated_minutes_total": today_payload.get("estimated_minutes_total", 0),
                },
            }
        )
