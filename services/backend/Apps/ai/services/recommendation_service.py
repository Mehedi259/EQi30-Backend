"""
Recommendation service for the EQi-30 AI service.

Orchestrates competency recommendation:

1. Accepts competency scores (from scoring pipeline or wire request).
2. Resolves the recommendation strategy version.
3. Validates input via the strategy.
4. Delegates ranking to the strategy.
5. Validates the output (exactly 6, unique codes, priority permutation 1..6).
6. Produces a structured ``RecommendationResult``.
7. Can map to wire ``CompetencyRecommendationResponse``.

This module contains **zero** ranking logic.  All priority assignment is
delegated to the registered ``RecommendationStrategy`` implementation.

Pipeline position::

    ScoringResult (domain)
         ↓
    RecommendationService.recommend()
         ↓  delegates to RecommendationStrategy.rank()
    RecommendationResult (domain)
         ↓  mapped via to_response()
    CompetencyRecommendationResponse (wire)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from Apps.ai.core.logging import get_logger
from Apps.ai.domain import get_taxonomy, is_taxonomy_specified
from Apps.ai.domain.recommendation import (
    COMPETENCY_COUNT,
    CompetencyRecommendationItem,
    CompetencyScoreInput,
    RecommendationInputError,
    RecommendationMethodologyNotConfigured,
    RecommendationResult,
    RecommendationStatus,
    RecommendationStrategyRegistry,
    RecommendationValidationError,
    get_recommendation_registry,
)
from Apps.ai.domain.scoring import CompetencyScoreResult, ScoringResult
from Apps.ai.schemas.recommendation import (
    CompetencyRecommendation,
    CompetencyRecommendationRequest,
    CompetencyRecommendationResponse,
)

logger = get_logger(__name__)


class RecommendationService:
    """Orchestrates competency recommendation through pluggable strategies.

    Contains **zero** ranking logic.
    """

    def __init__(
        self,
        registry: Optional[RecommendationStrategyRegistry] = None,
    ) -> None:
        self._registry = registry or get_recommendation_registry()

    # ------------------------------------------------------------------
    # Primary API: recommend from domain ScoringResult
    # ------------------------------------------------------------------

    def recommend(
        self,
        scoring_result: ScoringResult,
        *,
        recommendation_version: Optional[str] = None,
        user_ref: Optional[str] = None,
        request_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> RecommendationResult:
        """Produce a competency recommendation from scoring results.

        Raises:
            RecommendationMethodologyNotConfigured: no strategy registered.
            UnsupportedRecommendationVersion: version not found.
            RecommendationInputError: strategy-specific validation failure.
            RecommendationValidationError: strategy output fails structural
                validation (not exactly 6, bad priorities, etc.).
        """
        version = self._resolve_version(recommendation_version)

        if self._registry.is_empty:
            raise RecommendationMethodologyNotConfigured(version)

        strategy = self._registry.get(version)

        # Build domain-internal score inputs
        score_inputs = self._to_score_inputs(scoring_result.competency_scores)
        ctx = context or {}

        # Validate input count
        self._validate_input_count(score_inputs)

        # Validate references against the canonical taxonomy, when available
        self._validate_competency_references(score_inputs)

        # Strategy-specific validation
        strategy.validate_input(score_inputs, ctx)

        # Rank
        items = strategy.rank(score_inputs, ctx)

        # Validate output
        self._validate_output(items, version)

        ref = user_ref or scoring_result.user_ref

        logger.info(
            f"Recommendation produced for user_ref={ref!r} "
            f"using strategy v{version} "
            f"({len(items)} competencies ranked)."
        )

        return RecommendationResult(
            user_ref=ref,
            recommendation_version=version,
            status=RecommendationStatus.RECOMMENDED,
            recommendations=items,
            request_id=request_id or scoring_result.request_id,
            metadata={
                "recommendation_strategy": strategy.description,
                "scoring_version": scoring_result.scoring_version,
            },
        )

    # ------------------------------------------------------------------
    # Wire API: recommend from wire request
    # ------------------------------------------------------------------

    def recommend_from_request(
        self,
        request: CompetencyRecommendationRequest,
    ) -> CompetencyRecommendationResponse:
        """Produce a recommendation directly from a wire request.

        Convenience method for direct API usage.
        """
        version = self._resolve_version(request.recommendation_version)

        if self._registry.is_empty:
            raise RecommendationMethodologyNotConfigured(version)

        strategy = self._registry.get(version)

        # Transform wire CompetencyScore → domain CompetencyScoreInput
        score_inputs = [
            CompetencyScoreInput(
                competency_code=cs.competency_code,
                score=cs.score,
                scale_min=cs.scale_min,
                scale_max=cs.scale_max,
            )
            for cs in request.competency_scores
        ]

        ctx = dict(request.context)

        self._validate_input_count(score_inputs)
        self._validate_competency_references(score_inputs)
        strategy.validate_input(score_inputs, ctx)

        items = strategy.rank(score_inputs, ctx)
        self._validate_output(items, version)

        # Map domain → wire
        wire_recs = [
            CompetencyRecommendation(
                competency_code=item.competency_code,
                ai_priority=item.ai_priority,
                rationale=item.rationale,
                metadata=item.metadata,
            )
            for item in items
        ]

        return CompetencyRecommendationResponse(
            user_ref=request.user_ref,
            recommendation_version=version,
            recommendations=wire_recs,
            request_id=request.request_id,
            metadata={
                "recommendation_strategy": strategy.description,
            },
        )

    # ------------------------------------------------------------------
    # Mapping: domain → wire
    # ------------------------------------------------------------------

    @staticmethod
    def to_response(
        result: RecommendationResult,
    ) -> CompetencyRecommendationResponse:
        """Map a domain ``RecommendationResult`` to wire response."""
        wire_recs = [
            CompetencyRecommendation(
                competency_code=item.competency_code,
                ai_priority=item.ai_priority,
                rationale=item.rationale,
                metadata=item.metadata,
            )
            for item in result.recommendations
        ]
        return CompetencyRecommendationResponse(
            user_ref=result.user_ref,
            recommendation_version=result.recommendation_version,
            recommendations=wire_recs,
            request_id=result.request_id,
            metadata=result.metadata,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_version(self, requested: Optional[str]) -> str:
        if requested is not None:
            return requested
        default = self._registry.default_version
        if default is None:
            raise RecommendationMethodologyNotConfigured("(default)")
        return default

    @staticmethod
    def _to_score_inputs(
        scores: List[CompetencyScoreResult],
    ) -> List[CompetencyScoreInput]:
        return [
            CompetencyScoreInput(
                competency_code=cs.competency_code,
                score=cs.score,
                scale_min=cs.scale_min,
                scale_max=cs.scale_max,
            )
            for cs in scores
        ]

    @staticmethod
    def _validate_input_count(scores: List[CompetencyScoreInput]) -> None:
        if len(scores) != COMPETENCY_COUNT:
            raise RecommendationInputError(
                f"Expected exactly {COMPETENCY_COUNT} competency scores, "
                f"got {len(scores)}.",
                details={
                    "expected": COMPETENCY_COUNT,
                    "received": len(scores),
                },
            )
        # Unique codes
        codes = [s.competency_code for s in scores]
        seen: set[str] = set()
        duplicates: list[str] = []
        for c in codes:
            if c in seen and c not in duplicates:
                duplicates.append(c)
            seen.add(c)
        if duplicates:
            raise RecommendationInputError(
                f"Duplicate competency codes in input: {duplicates}",
                details={"duplicate_codes": duplicates},
            )

    @staticmethod
    def _validate_competency_references(scores: List[CompetencyScoreInput]) -> None:
        """Validate codes against the canonical taxonomy when it is available.

        Mirrors ``JourneyRecommendationService``'s graceful-degradation
        pattern: the approved taxonomy has not been supplied yet, so
        unresolvable references are skipped (logged) rather than blocked;
        once the taxonomy is registered this becomes a hard check
        automatically, with no code change required here.
        """
        if not is_taxonomy_specified():
            logger.debug(
                "Canonical taxonomy not specified; skipping competency "
                "reference validation."
            )
            return

        taxonomy = get_taxonomy()
        unknown = [
            s.competency_code
            for s in scores
            if not taxonomy.has_competency(s.competency_code)
        ]
        if unknown:
            raise RecommendationInputError(
                f"Unknown competency references: {unknown}",
                details={
                    "unknown_codes": unknown,
                    "known_codes": sorted(taxonomy.competency_codes),
                },
            )

    @staticmethod
    def _validate_output(
        items: List[CompetencyRecommendationItem],
        version: str,
    ) -> None:
        """Validate that strategy output meets structural requirements."""
        if len(items) != COMPETENCY_COUNT:
            raise RecommendationValidationError(
                f"Strategy v{version} returned {len(items)} recommendations, "
                f"expected exactly {COMPETENCY_COUNT}.",
                details={"count": len(items), "expected": COMPETENCY_COUNT},
            )

        codes = [i.competency_code for i in items]
        seen: set[str] = set()
        dup_codes: list[str] = []
        for c in codes:
            if c in seen and c not in dup_codes:
                dup_codes.append(c)
            seen.add(c)
        if dup_codes:
            raise RecommendationValidationError(
                f"Strategy v{version} produced duplicate competency codes: "
                f"{dup_codes}",
                details={"duplicate_codes": dup_codes},
            )

        priorities = sorted(i.ai_priority for i in items)
        expected = list(range(1, COMPETENCY_COUNT + 1))
        if priorities != expected:
            raise RecommendationValidationError(
                f"Strategy v{version} produced invalid priority set "
                f"{priorities}, expected {expected}.",
                details={"priorities": priorities, "expected": expected},
            )


__all__ = [
    "RecommendationService",
]
