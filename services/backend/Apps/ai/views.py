import logging
from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Apps.ai.core.exceptions import AppException
from Apps.ai.dependencies import (
    get_assessment_analysis_service,
    get_chat_service,
    get_journey_recommendation_service,
)
from Apps.ai.providers.openai_provider import OpenAIProviderSettings
from Apps.ai.schemas.assessment import AssessmentRequest
from Apps.ai.schemas.chat import ChatRequest
from Apps.ai.schemas.journey import JourneyRecommendationRequest
from Apps.ai.services.user_context import (
    IsAuthenticatedOrActiveOnboardingSession,
    build_grounded_suggestions,
    build_user_ai_context,
)

logger = logging.getLogger(__name__)


def _execute_ai_call(coroutine_fn):
    """Execute an async AI service call with uniform AppException error mapping."""
    try:
        return Response(async_to_sync(coroutine_fn)(), status=status.HTTP_200_OK)
    except AppException as exc:
        logger.warning(f"AI Exception: {exc.message}")
        return Response(
            {"error": exc.code, "message": exc.message, "details": exc.details},
            status=exc.status_code,
        )
    except Exception:
        logger.exception("Unexpected AI Exception")
        return Response(
            {"error": "INTERNAL_SERVER_ERROR", "message": "Unexpected error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class AssessmentAnalyzeView(APIView):
    """POST /api/v1/ai/assessment/analyze/ — stateless EQ assessment analysis."""

    permission_classes = [IsAuthenticatedOrActiveOnboardingSession]

    def post(self, request, *args, **kwargs):
        try:
            payload = AssessmentRequest(**request.data)
        except Exception as exc:
            return Response(
                {"error": "Validation Error", "details": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        service = get_assessment_analysis_service()
        request_id = request.headers.get("X-Request-ID")

        async def _call():
            res = await service.analyze(payload, request_id=request_id)
            return res.model_dump()

        return _execute_ai_call(_call)


class JourneyRecommendView(APIView):
    """POST /api/v1/ai/journey/recommend/ — personalized journey recommendation."""

    permission_classes = [IsAuthenticatedOrActiveOnboardingSession]

    def post(self, request, *args, **kwargs):
        try:
            payload = JourneyRecommendationRequest(**request.data)
        except Exception as exc:
            return Response(
                {"error": "Validation Error", "details": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        service = get_journey_recommendation_service()
        request_id = request.headers.get("X-Request-ID")

        async def _call():
            res = await service.recommend_from_request(payload, request_id=request_id)
            return res.model_dump()

        return _execute_ai_call(_call)


class ChatRespondView(APIView):
    """POST /api/v1/ai/chat/respond/ — grounded conversational coaching."""

    permission_classes = [IsAuthenticatedOrActiveOnboardingSession]

    def post(self, request, *args, **kwargs):
        raw_payload = dict(request.data) if isinstance(request.data, dict) else {}
        if request.user and request.user.is_authenticated:
            if not raw_payload.get("user_ref") or raw_payload.get("user_ref") == "anonymous":
                raw_payload["user_ref"] = f"user-{request.user.id}"
            raw_payload["context"] = build_user_ai_context(
                request.user, raw_payload.get("context")
            )
        try:
            payload = ChatRequest(**raw_payload)
        except Exception as exc:
            return Response(
                {"error": "Validation Error", "details": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        service = get_chat_service()
        request_id = request.headers.get("X-Request-ID")

        async def _call():
            res = await service.respond(payload, request_id=request_id)
            return res.model_dump()

        return _execute_ai_call(_call)


class ChatAssessmentAnalyzeView(APIView):
    """POST /api/v1/ai/chat/analyze/ — score assessment from chat history."""

    permission_classes = [IsAuthenticatedOrActiveOnboardingSession]

    def post(self, request, *args, **kwargs):
        history = request.data.get("history", [])
        if not isinstance(history, list):
            return Response(
                {"error": "Validation Error", "details": "history must be a list"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        service = get_chat_service()
        return _execute_ai_call(lambda: service.analyze_chat_for_assessment(history))


class AiSuggestionsView(APIView):
    """GET /api/v1/ai/suggestions/ — personalized EQ suggestions from reflections & scores."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        payload = build_grounded_suggestions(request.user)
        try:
            ai_settings = OpenAIProviderSettings()
            if ai_settings.api_key:
                chat_req = ChatRequest(
                    user_ref=f"user-{request.user.id}",
                    message=(
                        "Give one concise 2-sentence encouraging coaching suggestion based on "
                        "my recent EQ reflections and active abilities."
                    ),
                    history=[],
                    context=build_user_ai_context(request.user),
                )
                service = get_chat_service()
                chat_res = async_to_sync(service.respond)(
                    chat_req, request_id=request.headers.get("X-Request-ID")
                )
                if not chat_res.safety_blocked and chat_res.reply:
                    payload["ai_coach_note"] = chat_res.reply
        except Exception as exc:
            logger.warning(f"AI suggestions live enhancement skipped: {exc}")
        return Response(payload, status=status.HTTP_200_OK)
