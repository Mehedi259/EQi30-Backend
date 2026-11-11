from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from Apps.journey.services import ensure_journey, maybe_complete_journey, refresh_journey_day
from Apps.progress.serializers import BadgeSerializer
from Apps.progress.services import evaluate_badges

from .models import AbilityDayContent, DailyReflection, UserDailySession, WeeklyCheckIn
from .serializers import (
    AbilityDayContentSerializer,
    DailyReflectionSerializer,
    UserDailySessionSerializer,
    WeeklyCheckInSerializer,
)


class AbilityDayContentView(APIView):
    """Daily learning content for an ability (teaching, practice, plan, reflection)."""

    @extend_schema(responses=AbilityDayContentSerializer)
    def get(self, request, ability_id, day_number):
        content = get_object_or_404(
            AbilityDayContent,
            ability_id=ability_id,
            ability__is_active=True,
            day_number=day_number,
        )
        return Response(AbilityDayContentSerializer(content).data)


class CompleteSessionView(APIView):
    """Complete a session; progress, journey state and badges update from it."""

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        session = get_object_or_404(UserDailySession, pk=pk, user=request.user)
        new_badges = []
        if session.status != UserDailySession.Status.COMPLETED:
            session.status = UserDailySession.Status.COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at"])
            maybe_complete_journey(session.journey)
            new_badges = evaluate_badges(request.user)

        journey = session.journey
        return Response(
            {
                "session": UserDailySessionSerializer(session).data,
                "journey": {
                    "status": journey.status,
                    "current_day": journey.current_day,
                    "total_days": journey.total_days,
                }
                if journey
                else None,
                "new_badges": BadgeSerializer(new_badges, many=True).data,
            }
        )


class SessionReflectionView(APIView):
    @extend_schema(request=DailyReflectionSerializer, responses={201: DailyReflectionSerializer})
    def post(self, request, pk):
        session = get_object_or_404(UserDailySession, pk=pk, user=request.user)
        serializer = DailyReflectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reflection, _ = DailyReflection.objects.update_or_create(
            session=session,
            defaults={"user": request.user, **serializer.validated_data},
        )
        return Response(
            DailyReflectionSerializer(reflection).data, status=status.HTTP_201_CREATED
        )


class WeeklyCheckInView(APIView):
    """Check weekly check-in eligibility/real summary and submit weekly check-ins."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        journey = refresh_journey_day(ensure_journey(request.user))
        current_day = max(journey.current_day or 1, 1)
        week_number = ((current_day - 1) // 7) + 1
        already_submitted = WeeklyCheckIn.objects.filter(
            user=request.user,
            journey=journey,
            week_number=week_number,
        ).exists()

        week_start_day = (week_number - 1) * 7 + 1
        week_end_day = week_number * 7
        week_sessions = (
            UserDailySession.objects.filter(
                user=request.user,
                journey=journey,
                status=UserDailySession.Status.COMPLETED,
                day_number__gte=week_start_day,
                day_number__lte=week_end_day,
            )
            .select_related("ability")
            .order_by("day_number", "id")
        )
        seen_abilities = set()
        skills_practiced = []
        for sess in week_sessions:
            if sess.ability_id not in seen_abilities:
                seen_abilities.add(sess.ability_id)
                skills_practiced.append(sess.ability.name)

        eligible = (
            current_day >= 7
            and not already_submitted
            and week_sessions.exists()
        )
        return Response(
            {
                "eligible": eligible,
                "week_number": week_number,
                "already_submitted": already_submitted,
                "skills_count": len(skills_practiced),
                "skills_practiced": skills_practiced,
            }
        )

    @extend_schema(request=WeeklyCheckInSerializer, responses={201: WeeklyCheckInSerializer})
    def post(self, request):
        serializer = WeeklyCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        journey = ensure_journey(request.user)
        checkin, _ = WeeklyCheckIn.objects.update_or_create(
            user=request.user,
            journey=journey,
            week_number=serializer.validated_data["week_number"],
            defaults={"answers": serializer.validated_data.get("answers", {})},
        )
        return Response(
            WeeklyCheckInSerializer(checkin).data, status=status.HTTP_201_CREATED
        )
