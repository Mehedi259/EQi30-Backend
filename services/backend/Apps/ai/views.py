from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from Apps.ai.schemas.assessment import AssessmentRequest
from Apps.ai.schemas.journey import JourneyRecommendationRequest
from Apps.ai.schemas.chat import ChatRequest
from Apps.ai.dependencies import (
    get_assessment_analysis_service,
    get_journey_recommendation_service,
    get_chat_service,
)
from Apps.ai.core.exceptions import AppException
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

class AssessmentAnalyzeView(APIView):
    """
    POST /api/v1/ai/assessment/analyze
    Runs the full stateless AI pipeline over a submitted assessment.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            payload = AssessmentRequest(**request.data)
        except Exception as e:
            return Response({"error": "Validation Error", "details": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        service = get_assessment_analysis_service()
        try:
            result = async_to_sync(service.analyze)(payload, request_id=request.headers.get("X-Request-ID"))
            return Response(result.model_dump(), status=status.HTTP_200_OK)
        except AppException as e:
            logger.warning(f"AI Exception: {e.message}")
            return Response({"error": e.code, "message": e.message, "details": e.details}, status=e.status_code)
        except Exception as e:
            logger.exception("Unexpected AI Exception")
            return Response({"error": "INTERNAL_SERVER_ERROR", "message": "Unexpected error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class JourneyRecommendView(APIView):
    """
    POST /api/v1/ai/journey/recommend
    Recommends a personalized learning journey based on assessment scores.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            payload = JourneyRecommendationRequest(**request.data)
        except Exception as e:
            return Response({"error": "Validation Error", "details": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        service = get_journey_recommendation_service()
        try:
            result = async_to_sync(service.recommend_from_request)(payload, request_id=request.headers.get("X-Request-ID"))
            return Response(result.model_dump(), status=status.HTTP_200_OK)
        except AppException as e:
            logger.warning(f"AI Exception: {e.message}")
            return Response({"error": e.code, "message": e.message, "details": e.details}, status=e.status_code)
        except Exception as e:
            logger.exception("Unexpected AI Exception")
            return Response({"error": "INTERNAL_SERVER_ERROR", "message": "Unexpected error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatRespondView(APIView):
    """
    POST /api/v1/ai/chat/respond
    Provides conversational coaching.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            payload = ChatRequest(**request.data)
        except Exception as e:
            return Response({"error": "Validation Error", "details": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        service = get_chat_service()
        try:
            result = async_to_sync(service.respond)(payload, request_id=request.headers.get("X-Request-ID"))
            return Response(result.model_dump(), status=status.HTTP_200_OK)
        except AppException as e:
            logger.warning(f"AI Exception: {e.message}")
            return Response({"error": e.code, "message": e.message, "details": e.details}, status=e.status_code)
        except Exception as e:
            logger.exception("Unexpected AI Exception")
            return Response({"error": "INTERNAL_SERVER_ERROR", "message": "Unexpected error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChatAssessmentAnalyzeView(APIView):
    """
    POST /api/v1/ai/chat/analyze/
    Analyzes chat history to generate EQ assessment scores.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        history = request.data.get("history", [])
        if not isinstance(history, list):
            return Response({"error": "Validation Error", "details": "history must be a list"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        service = get_chat_service()
        try:
            result = async_to_sync(service.analyze_chat_for_assessment)(history)
            return Response(result, status=status.HTTP_200_OK)
        except AppException as e:
            logger.warning(f"AI Exception: {e.message}")
            return Response({"error": e.code, "message": e.message, "details": e.details}, status=e.status_code)
        except Exception as e:
            logger.exception("Unexpected AI Exception")
            return Response({"error": "INTERNAL_SERVER_ERROR", "message": "Unexpected error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
