from typing import Optional
import httpx
from django.conf import settings

from Apps.ai.providers.openai_provider import OpenAIProvider, OpenAIProviderSettings
from Apps.ai.services.analysis_service import AssessmentAnalysisService
from Apps.ai.services.journey_service import JourneyRecommendationService
from Apps.ai.services.chat_service import ChatService
from Apps.ai.services.safety_service import SafetyService
from Apps.ai.services.context_service import ContextService
from Apps.ai.services.scoring_service import ScoringService
from Apps.ai.services.recommendation_service import RecommendationService

def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient()

def get_openai_provider() -> OpenAIProvider:
    provider_settings = OpenAIProviderSettings()
    return OpenAIProvider(settings=provider_settings, http_client=get_http_client())

def get_safety_service() -> SafetyService:
    return SafetyService()

def get_scoring_service() -> ScoringService:
    return ScoringService()

def get_recommendation_service() -> RecommendationService:
    return RecommendationService()

def get_context_service() -> ContextService:
    return ContextService()

def get_assessment_analysis_service() -> AssessmentAnalysisService:
    return AssessmentAnalysisService(
        scoring_service=get_scoring_service(),
        recommendation_service=get_recommendation_service()
    )

def get_journey_recommendation_service() -> JourneyRecommendationService:
    return JourneyRecommendationService()

def get_chat_service() -> ChatService:
    return ChatService(
        provider=get_openai_provider(),
        safety_service=get_safety_service(),
        context_service=get_context_service()
    )
