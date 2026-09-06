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

# Globals to act as singletons for the services (similar to FastAPI dependencies)
_http_client: Optional[httpx.AsyncClient] = None
_openai_provider: Optional[OpenAIProvider] = None

def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client

def get_openai_provider() -> OpenAIProvider:
    global _openai_provider
    if _openai_provider is None:
        provider_settings = OpenAIProviderSettings()
        _openai_provider = OpenAIProvider(settings=provider_settings, http_client=get_http_client())
    return _openai_provider

def get_safety_service() -> SafetyService:
    return SafetyService(provider=get_openai_provider())

def get_scoring_service() -> ScoringService:
    return ScoringService()

def get_recommendation_service() -> RecommendationService:
    return RecommendationService()

def get_context_service() -> ContextService:
    return ContextService()

def get_assessment_analysis_service() -> AssessmentAnalysisService:
    return AssessmentAnalysisService(
        scoring=get_scoring_service(),
        recommendation=get_recommendation_service(),
        safety=get_safety_service()
    )

def get_journey_recommendation_service() -> JourneyRecommendationService:
    return JourneyRecommendationService()

def get_chat_service() -> ChatService:
    return ChatService(
        provider=get_openai_provider(),
        safety=get_safety_service(),
        context=get_context_service()
    )
