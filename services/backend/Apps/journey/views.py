from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import (
    AnonymousOnboardingSession,
    AssessmentResult,
    GrowthPlan,
    GuidedJourneyImage,
    PracticeTimeOption,
)
from .serializers import (
    AssessmentSubmitSerializer,
    GrowthPlanSelectSerializer,
    GrowthPlanSerializer,
    GuidedJourneyImageSerializer,
    PracticeTimeOptionSerializer,
    PracticeTimeSelectSerializer,
    PrioritiesUpdateSerializer,
    SessionStateSerializer,
)


class SessionExpired(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "Onboarding session has expired."
    default_code = "session_expired"


class SessionAlreadyClaimed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Onboarding session has already been claimed."
    default_code = "session_claimed"


def get_active_session(session_uuid):
    try:
        session = AnonymousOnboardingSession.objects.get(session_uuid=session_uuid)
    except AnonymousOnboardingSession.DoesNotExist:
        raise NotFound("Onboarding session not found.")
    if session.status == AnonymousOnboardingSession.Status.CLAIMED:
        raise SessionAlreadyClaimed()
    if session.is_expired:
        session.delete()  # anonymous data is deleted once the window passes
        raise SessionExpired()
    return session


# ---------------------------------------------------------------------------
# Anonymous onboarding (no authentication required)
# ---------------------------------------------------------------------------

class OnboardingSessionCreateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={201: SessionStateSerializer})
    def post(self, request):
        services.purge_expired_sessions()
        session = AnonymousOnboardingSession.objects.create()
        return Response(
            SessionStateSerializer(session).data, status=status.HTTP_201_CREATED
        )


class OnboardingAssessmentView(APIView):
    """Receive / return the AI assessment for an anonymous session."""

    permission_classes = [AllowAny]

    @extend_schema(responses=SessionStateSerializer)
    def get(self, request, session_uuid):
        session = get_active_session(session_uuid)
        return Response(SessionStateSerializer(session).data)

    @extend_schema(request=AssessmentSubmitSerializer, responses={201: SessionStateSerializer})
    def post(self, request, session_uuid):
        session = get_active_session(session_uuid)
        serializer = AssessmentSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            # A new assessment replaces the previous one entirely.
            session.assessment_results.all().delete()
            AssessmentResult.objects.bulk_create(
                AssessmentResult(
                    session=session,
                    competency=entry["competency"],
                    score=entry["score"],
                    ai_priority=entry["ai_priority"],
                )
                for entry in serializer.validated_data["results"]
            )
        return Response(
            SessionStateSerializer(session).data, status=status.HTTP_201_CREATED
        )


class OnboardingPrioritiesView(APIView):
    """Accept the AI order or store a customized order (never touches ai_priority)."""

    permission_classes = [AllowAny]

    @extend_schema(request=PrioritiesUpdateSerializer, responses=SessionStateSerializer)
    def patch(self, request, session_uuid):
        session = get_active_session(session_uuid)
        serializer = PrioritiesUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not session.assessment_results.exists():
            return Response(
                {"detail": "Submit the assessment before setting priorities."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            session.journey_type = data["journey_type"]
            session.save(update_fields=["journey_type"])
            for entry in data.get("priorities", []):
                session.assessment_results.filter(
                    competency=entry["competency"]
                ).update(user_priority=entry["priority"])
        return Response(SessionStateSerializer(session).data)


class OnboardingGrowthPlanView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=GrowthPlanSelectSerializer, responses=SessionStateSerializer)
    def put(self, request, session_uuid):
        session = get_active_session(session_uuid)
        serializer = GrowthPlanSelectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session.growth_plan = serializer.validated_data["growth_plan"]
        session.save(update_fields=["growth_plan"])
        return Response(SessionStateSerializer(session).data)


class OnboardingPracticeTimeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PracticeTimeSelectSerializer, responses=SessionStateSerializer)
    def put(self, request, session_uuid):
        session = get_active_session(session_uuid)
        serializer = PracticeTimeSelectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session.practice_time = serializer.validated_data["practice_time"]
        session.save(update_fields=["practice_time"])
        return Response(SessionStateSerializer(session).data)


# Simple catalog endpoints for the onboarding screens.

class GrowthPlanListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = GrowthPlanSerializer
    queryset = GrowthPlan.objects.filter(is_active=True)


class PracticeTimeListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PracticeTimeOptionSerializer
    queryset = PracticeTimeOption.objects.all()


class GuidedJourneyListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = GuidedJourneyImageSerializer
    queryset = (
        GuidedJourneyImage.objects.filter(is_active=True).select_related("competency")
    )


# ---------------------------------------------------------------------------
# Personalized journey (authenticated)
# ---------------------------------------------------------------------------

class JourneyView(APIView):
    """The six competency sections in the user's personalized order."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(services.journey_overview(request.user))


class JourneyTodayView(APIView):
    """Today's sessions (count follows the growth pace)."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(services.journey_today(request.user))


class JourneyHistoryView(APIView):
    """All journeys of the user with completion stats."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(services.journey_history(request.user))
