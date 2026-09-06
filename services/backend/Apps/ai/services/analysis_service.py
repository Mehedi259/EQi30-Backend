"""
Assessment analysis orchestrator.

Owns the end-to-end pipeline so the API route stays a thin transport layer::

    AssessmentService.process()      → validate, transform  (AssessmentResult)
         ↓
    ScoringService.score()           → delegate to strategy (ScoringResult)
         ↓
    RecommendationService.recommend()→ delegate to strategy (RecommendationResult)
         ↓
    AssessmentAnalysisResponse       → wire contract

This class contains **zero** psychometric and **zero** ranking logic. It
sequences the three services and maps their output onto the wire contract.
Every failure it can encounter is a typed ``AppException`` raised by a
service, which propagates to the registered global handlers — this
orchestrator never swallows an error or substitutes a fabricated result.
"""

from __future__ import annotations

from typing import Optional

from Apps.ai.core.logging import get_logger
from Apps.ai.domain.assessment import AssessmentResult
from Apps.ai.domain.recommendation import RecommendationResult
from Apps.ai.domain.scoring import ScoringResult
from Apps.ai.schemas.analysis import AssessmentAnalysisResponse
from Apps.ai.schemas.assessment import AssessmentRequest, CompetencyScore
from Apps.ai.schemas.recommendation import CompetencyRecommendation
from Apps.ai.services.assessment_service import AssessmentService
from Apps.ai.services.recommendation_service import RecommendationService
from Apps.ai.services.scoring_service import ScoringService

logger = get_logger(__name__)


class AssessmentAnalysisService:
    """Runs validate → score → recommend and maps the result to the wire."""

    def __init__(
        self,
        assessment_service: Optional[AssessmentService] = None,
        scoring_service: Optional[ScoringService] = None,
        recommendation_service: Optional[RecommendationService] = None,
    ) -> None:
        self._assessment = assessment_service or AssessmentService()
        self._scoring = scoring_service or ScoringService()
        self._recommendation = recommendation_service or RecommendationService()

    def analyze(
        self,
        request: AssessmentRequest,
        *,
        request_id: Optional[str] = None,
    ) -> AssessmentAnalysisResponse:
        """Execute the full analysis pipeline.

        Raises:
            AssessmentError: intake validation failed (422).
            ScoringMethodologyNotConfigured: no scoring strategy registered (501).
            UnsupportedScoringVersion: unknown scoring version (422).
            ScoringInputError: methodology-specific validation failed (422).
            RecommendationMethodologyNotConfigured: no strategy registered (501).
            RecommendationValidationError: strategy produced invalid output (500).
        """
        correlation_id = request_id or request.request_id

        assessment_result: AssessmentResult = self._assessment.process(request)

        scoring_result: ScoringResult = self._scoring.score(assessment_result)

        recommendation_result: RecommendationResult = self._recommendation.recommend(
            scoring_result,
            request_id=correlation_id,
        )

        logger.info(
            f"Assessment analysis complete: user_ref={request.user_ref!r}, "
            f"scoring_version={scoring_result.scoring_version!r}, "
            f"recommendation_version={recommendation_result.recommendation_version!r}"
        )

        return self._to_response(
            assessment_result=assessment_result,
            scoring_result=scoring_result,
            recommendation_result=recommendation_result,
            request_id=correlation_id,
        )

    @staticmethod
    def _to_response(
        *,
        assessment_result: AssessmentResult,
        scoring_result: ScoringResult,
        recommendation_result: RecommendationResult,
        request_id: Optional[str],
    ) -> AssessmentAnalysisResponse:
        return AssessmentAnalysisResponse(
            user_ref=scoring_result.user_ref,
            instrument_version=scoring_result.instrument_version,
            scoring_version=scoring_result.scoring_version,
            recommendation_version=recommendation_result.recommendation_version,
            competency_scores=[
                CompetencyScore(
                    competency_code=cs.competency_code,
                    score=cs.score,
                    scale_min=cs.scale_min,
                    scale_max=cs.scale_max,
                    ability_scores=cs.ability_scores,
                )
                for cs in scoring_result.competency_scores
            ],
            recommendations=[
                CompetencyRecommendation(
                    competency_code=item.competency_code,
                    ai_priority=item.ai_priority,
                    rationale=item.rationale,
                    metadata=item.metadata,
                )
                for item in recommendation_result.ordered()
            ],
            validation_warnings=list(assessment_result.validation_warnings),
            request_id=request_id,
            metadata={
                "scoring_strategy": scoring_result.metadata.get("scoring_strategy"),
                "recommendation_strategy": recommendation_result.metadata.get(
                    "recommendation_strategy"
                ),
            },
        )


__all__ = ["AssessmentAnalysisService"]
