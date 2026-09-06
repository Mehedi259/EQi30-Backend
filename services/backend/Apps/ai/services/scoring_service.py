"""
Scoring service for the EQi-30 AI service.

Orchestrates the scoring pipeline:

1. Accepts a validated ``AssessmentResult`` from the assessment service.
2. Resolves the scoring version (explicit or registry default).
3. Retrieves the ``ScoringStrategy`` from the registry.
4. Delegates methodology-specific validation and scoring.
5. Produces a structured ``ScoringResult`` (domain).
6. Can map the result to the wire-contract ``AssessmentResponse``.

This module contains **zero** psychometric logic.  All scoring behaviour
is delegated to the registered ``ScoringStrategy`` implementation.

Pipeline position::

    AssessmentService.process()
         ↓  produces AssessmentResult
    ScoringService.score()
         ↓  delegates to ScoringStrategy
    ScoringResult (domain)
         ↓  mapped via to_assessment_response()
    AssessmentResponse (wire schema)
"""

from __future__ import annotations

from typing import List, Optional

from Apps.ai.core.logging import get_logger
from Apps.ai.domain.assessment import AssessmentResult
from Apps.ai.domain.scoring import (
    CompetencyScoreResult,
    ScoringMethodologyNotConfigured,
    ScoringResult,
    ScoringStatus,
    ScoringStrategy,
    ScoringStrategyRegistry,
    get_scoring_registry,
)
from Apps.ai.schemas.assessment import (
    AssessmentRequest,
    AssessmentResponse,
    CompetencyScore,
)

logger = get_logger(__name__)


class ScoringService:
    """Orchestrates assessment scoring through pluggable strategies.

    This class validates input, resolves the scoring version, delegates to
    the registered ``ScoringStrategy`` and packages the structured result.
    It contains **zero** psychometric logic.
    """

    def __init__(
        self, registry: Optional[ScoringStrategyRegistry] = None
    ) -> None:
        self._registry = registry or get_scoring_registry()

    # ------------------------------------------------------------------
    # Primary API: score from domain AssessmentResult
    # ------------------------------------------------------------------

    def score(self, assessment_result: AssessmentResult) -> ScoringResult:
        """Score a validated assessment result.

        This is the primary entry point.  It receives the output of
        ``AssessmentService.process()`` and produces a ``ScoringResult``.

        Raises:
            ScoringMethodologyNotConfigured: when no strategies are
                registered at all, or the resolved version has no strategy.
            UnsupportedScoringVersion: when the requested version is not
                registered.
            ScoringInputError: when answers fail methodology-specific
                validation.
        """
        scoring_version = self._resolve_version(
            assessment_result.scoring_version
        )

        if self._registry.is_empty:
            raise ScoringMethodologyNotConfigured(scoring_version)

        strategy = self._registry.get(scoring_version)

        # Prepare answers as dicts for the strategy interface
        answers = [
            {"item_id": a.item_id, "value": a.value, "ability_code": a.ability_code}
            for a in assessment_result.assessment_input.answers
        ]

        # Methodology-specific validation
        strategy.validate_input(
            answers=answers,
            instrument_version=assessment_result.instrument_version,
        )

        # Compute scores
        competency_scores = strategy.compute_scores(
            answers=answers,
            instrument_version=assessment_result.instrument_version,
        )

        logger.info(
            f"Scored assessment for user_ref={assessment_result.user_ref!r} "
            f"using scoring v{scoring_version} "
            f"({len(competency_scores)} competency scores produced)."
        )

        return ScoringResult(
            user_ref=assessment_result.user_ref,
            instrument_version=assessment_result.instrument_version,
            scoring_version=scoring_version,
            status=ScoringStatus.SCORED,
            competency_scores=competency_scores,
            request_id=assessment_result.request_id,
            metadata={
                "scoring_strategy": strategy.description,
                "scoring_version": scoring_version,
                "answer_count": assessment_result.answer_count,
            },
        )

    # ------------------------------------------------------------------
    # Legacy API: score directly from wire schema (backward compat)
    # ------------------------------------------------------------------

    def score_assessment(
        self, request: AssessmentRequest
    ) -> AssessmentResponse:
        """Score an ``AssessmentRequest`` wire schema directly.

        This is a convenience method that bridges the wire schema to the
        domain pipeline and maps the result back to the wire response.
        Useful for direct API-layer integration before the full
        ``AssessmentService`` pipeline is wired in.
        """
        scoring_version = self._resolve_version(request.scoring_version)

        if self._registry.is_empty:
            raise ScoringMethodologyNotConfigured(scoring_version)

        strategy = self._registry.get(scoring_version)

        answers = [
            {"item_id": r.item_id, "value": r.value}
            for r in request.responses
        ]

        strategy.validate_input(
            answers=answers,
            instrument_version=request.instrument_version,
        )

        competency_scores = strategy.compute_scores(
            answers=answers,
            instrument_version=request.instrument_version,
        )

        logger.info(
            f"Scored assessment for user_ref={request.user_ref!r} "
            f"using scoring v{scoring_version} "
            f"({len(competency_scores)} competency scores produced)."
        )

        return AssessmentResponse(
            user_ref=request.user_ref,
            instrument_version=request.instrument_version,
            scoring_version=scoring_version,
            competency_scores=[
                CompetencyScore(
                    competency_code=cs.competency_code,
                    score=cs.score,
                    scale_min=cs.scale_min,
                    scale_max=cs.scale_max,
                    ability_scores=cs.ability_scores,
                )
                for cs in competency_scores
            ],
            request_id=request.request_id,
            metadata={"scoring_strategy": strategy.description},
        )

    # ------------------------------------------------------------------
    # Mapping: domain → wire
    # ------------------------------------------------------------------

    @staticmethod
    def to_assessment_response(
        scoring_result: ScoringResult,
    ) -> AssessmentResponse:
        """Map a domain ``ScoringResult`` to the wire ``AssessmentResponse``."""
        return AssessmentResponse(
            user_ref=scoring_result.user_ref,
            instrument_version=scoring_result.instrument_version,
            scoring_version=scoring_result.scoring_version,
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
            request_id=scoring_result.request_id,
            metadata=scoring_result.metadata,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_version(self, requested: Optional[str]) -> str:
        """Return the explicit version or fall back to the registry default."""
        if requested is not None:
            return requested

        default = self._registry.default_version
        if default is None:
            raise ScoringMethodologyNotConfigured("(default)")

        return default


__all__ = [
    "ScoringService",
]
