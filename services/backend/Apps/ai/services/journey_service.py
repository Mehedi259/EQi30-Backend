"""
Journey recommendation service for the EQi-30 AI service.

Orchestrates journey recommendation:

1. Validates competency references against the canonical taxonomy.
2. Validates exactly six competencies with unique codes.
3. Validates ``ai_priority`` forms the permutation 1..6.
4. Resolves and validates the user-selection schema version.
5. Resolves the journey strategy version.
6. Delegates generation to the registered ``JourneyRecommendationStrategy``.
7. Validates strategy output structurally.
8. Produces a ``JourneyRecommendationResult`` and can map it to the wire.

This module contains **zero** journey methodology and **zero** invented
user-selection taxonomy. All journey construction is delegated to the
registered strategy.

Persistence boundary
--------------------
This service is a pure function of its input. It opens no connection, holds
no session, writes no record and mutates no user, journey, progress or
priority state. It returns a value object; **Django performs all
persistence**. ``user_priority`` is neither accepted nor produced.

Pipeline position::

    RecommendationResult (ai_priority per competency)
         ↓
    JourneyRecommendationService.recommend()
         ↓  delegates to JourneyRecommendationStrategy.generate()
    JourneyRecommendationResult (domain)
         ↓  mapped via to_response()
    JourneyRecommendationResponse (wire)  → Django persists
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from Apps.ai.core.logging import get_logger
from Apps.ai.domain import get_taxonomy, is_taxonomy_specified
from Apps.ai.domain.journey import (
    COMPETENCY_COUNT,
    JourneyCompetencyInput,
    JourneyInputError,
    JourneyItem,
    JourneyMethodologyNotConfigured,
    JourneyRecommendationInput,
    JourneyRecommendationResult,
    JourneySelectionEnvelope,
    JourneyStatus,
    JourneyStrategyRegistry,
    JourneyValidationError,
    SelectionSchemaRegistry,
    get_journey_registry,
    get_selection_schema_registry,
)
from Apps.ai.schemas.journey import (
    JourneyRecommendationItem,
    JourneyRecommendationRequest,
    JourneyRecommendationResponse,
)

logger = get_logger(__name__)


class JourneyRecommendationService:
    """Orchestrates journey recommendation through pluggable strategies.

    Contains **zero** journey methodology and performs **zero** persistence.
    """

    def __init__(
        self,
        registry: Optional[JourneyStrategyRegistry] = None,
        selection_registry: Optional[SelectionSchemaRegistry] = None,
    ) -> None:
        self._registry = registry or get_journey_registry()
        self._selections = selection_registry or get_selection_schema_registry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(
        self,
        journey_input: JourneyRecommendationInput,
        *,
        journey_version: Optional[str] = None,
    ) -> JourneyRecommendationResult:
        """Produce a journey recommendation.

        Raises:
            JourneyInputError: competency set, priorities or references invalid.
            UnsupportedSelectionSchemaVersion: selection schema not registered.
            JourneyMethodologyNotConfigured: no strategy registered.
            UnsupportedJourneyVersion: requested version not registered.
            JourneyValidationError: strategy output fails structural validation.
        """
        warnings: List[str] = []

        # 1-3. Structural validation of the competency inputs.
        self._validate_competency_set(journey_input.competencies)
        self._validate_ai_priorities(journey_input.competencies)
        self._validate_competency_references(journey_input.competencies, warnings)

        # 4. Selection schema resolution.
        self._validate_selection(journey_input, warnings)

        # 5. Strategy resolution.
        version = self._resolve_version(
            journey_version or journey_input.journey_version
        )
        if self._registry.is_empty:
            raise JourneyMethodologyNotConfigured(version)
        strategy = self._registry.get(version)

        # 6. Delegate generation.
        strategy.validate_input(journey_input)
        items = strategy.generate(journey_input)

        # 7. Structural validation of strategy output.
        self._validate_output(items, version)

        logger.info(
            f"Journey recommendation produced for user_ref="
            f"{journey_input.user_ref!r} using strategy v{version} "
            f"({len(items)} items)."
        )

        # 8. Package. The version is preserved verbatim on the result.
        return JourneyRecommendationResult(
            user_ref=journey_input.user_ref,
            journey_version=version,
            selection_schema_version=(
                journey_input.selection.selection_schema_version
            ),
            status=JourneyStatus.RECOMMENDED,
            items=items,
            locale=journey_input.locale,
            request_id=journey_input.request_id,
            validation_warnings=warnings,
            metadata={
                "journey_strategy": strategy.description,
                "journey_version": version,
                "competency_count": len(journey_input.competencies),
            },
        )

    # ------------------------------------------------------------------
    # Wire API: recommend from wire request
    # ------------------------------------------------------------------

    def recommend_from_request(
        self,
        request: JourneyRecommendationRequest,
        *,
        request_id: Optional[str] = None,
    ) -> JourneyRecommendationResponse:
        """Produce a journey recommendation directly from a wire request.

        Convenience method for direct API-layer usage: transforms the wire
        schema into the domain input, delegates to :meth:`recommend`, and
        maps the domain result back to the wire response. Mirrors
        ``RecommendationService.recommend_from_request``.
        """
        journey_input = self._from_request(request, request_id=request_id)
        result = self.recommend(journey_input)
        return self.to_response(result)

    @staticmethod
    def _from_request(
        request: JourneyRecommendationRequest,
        *,
        request_id: Optional[str],
    ) -> JourneyRecommendationInput:
        """Map the wire request onto the domain input.

        Pure transformation only — no validation decisions are made here;
        every rule (six competencies, ai_priority permutation, selection
        schema, references) is enforced uniformly by ``recommend()`` for
        both the domain and wire entry points.
        """
        return JourneyRecommendationInput(
            user_ref=request.user_ref,
            competencies=[
                JourneyCompetencyInput(
                    competency_code=c.competency_code,
                    ai_priority=c.ai_priority,
                    score=c.score,
                    scale_min=c.scale_min,
                    scale_max=c.scale_max,
                )
                for c in request.competencies
            ],
            selection=JourneySelectionEnvelope(
                selection_schema_version=request.selection.selection_schema_version,
                selections=dict(request.selection.selections),
            ),
            locale=request.locale,
            journey_version=request.journey_version,
            assessment_context=dict(request.context),
            request_id=request_id or request.request_id,
        )

    # ------------------------------------------------------------------
    # Mapping: domain → wire
    # ------------------------------------------------------------------

    @staticmethod
    def to_response(
        result: JourneyRecommendationResult,
    ) -> JourneyRecommendationResponse:
        """Map a domain result to the wire response Django persists."""
        return JourneyRecommendationResponse(
            user_ref=result.user_ref,
            journey_version=result.journey_version,
            selection_schema_version=result.selection_schema_version,
            recommendations=[
                JourneyRecommendationItem(
                    reference=item.reference,
                    rank=item.rank,
                    rationale=item.rationale,
                    attributes=item.attributes,
                )
                for item in result.ordered()
            ],
            request_id=result.request_id,
            metadata=result.metadata,
        )

    # ------------------------------------------------------------------
    # Internal validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_competency_set(
        competencies: Sequence[JourneyCompetencyInput],
    ) -> None:
        """Exactly six competencies with unique codes."""
        if len(competencies) != COMPETENCY_COUNT:
            raise JourneyInputError(
                f"Expected exactly {COMPETENCY_COUNT} competencies, "
                f"got {len(competencies)}.",
                details={
                    "expected": COMPETENCY_COUNT,
                    "received": len(competencies),
                },
            )

        codes = [c.competency_code for c in competencies]
        duplicates = _duplicates(codes)
        if duplicates:
            raise JourneyInputError(
                f"Duplicate competency codes in journey input: {duplicates}",
                details={"duplicate_codes": duplicates},
            )

    @staticmethod
    def _validate_ai_priorities(
        competencies: Sequence[JourneyCompetencyInput],
    ) -> None:
        """``ai_priority`` must be exactly the permutation 1..6."""
        priorities = sorted(c.ai_priority for c in competencies)
        expected = list(range(1, COMPETENCY_COUNT + 1))
        if priorities != expected:
            raise JourneyInputError(
                f"ai_priority must be exactly {expected} with no gaps or "
                f"duplicates; got {priorities}.",
                details={"priorities": priorities, "expected": expected},
            )

    @staticmethod
    def _validate_competency_references(
        competencies: Sequence[JourneyCompetencyInput],
        warnings: List[str],
    ) -> None:
        """Validate codes against the canonical taxonomy when it is available.

        The approved taxonomy has not been supplied yet. Rather than block
        or invent one, unresolvable references are recorded as a warning; as
        soon as the taxonomy is registered this becomes a hard check.
        """
        if not is_taxonomy_specified():
            warnings.append(
                "Canonical taxonomy not specified. Competency reference "
                "validation skipped. Supply the approved taxonomy to enable "
                "full validation."
            )
            return

        taxonomy = get_taxonomy()
        unknown: List[str] = []
        for competency in competencies:
            if not taxonomy.has_competency(competency.competency_code):
                unknown.append(competency.competency_code)

        if unknown:
            raise JourneyInputError(
                f"Unknown competency references: {unknown}",
                details={
                    "unknown_codes": unknown,
                    "known_codes": sorted(taxonomy.competency_codes),
                },
            )

    def _validate_selection(
        self,
        journey_input: JourneyRecommendationInput,
        warnings: List[str],
    ) -> None:
        """Validate the selection envelope against its registered schema."""
        if self._selections.is_empty:
            warnings.append(
                f"No user-selection schema registered. Accepting selection "
                f"version "
                f"'{journey_input.selection.selection_schema_version}' without "
                f"payload validation. Register the approved taxonomy to enable "
                f"full validation."
            )
            return

        # Raises UnsupportedSelectionSchemaVersion or JourneyInputError.
        self._selections.validate(journey_input.selection)

    @staticmethod
    def _validate_output(items: Sequence[JourneyItem], version: str) -> None:
        """Validate structural properties of the strategy output."""
        references = [item.reference for item in items]
        duplicate_refs = _duplicates(references)
        if duplicate_refs:
            raise JourneyValidationError(
                f"Strategy v{version} produced duplicate journey references: "
                f"{duplicate_refs}",
                details={"duplicate_references": duplicate_refs},
            )

        ranks = [item.rank for item in items]
        duplicate_ranks = _duplicates(ranks)
        if duplicate_ranks:
            raise JourneyValidationError(
                f"Strategy v{version} produced duplicate ranks: {duplicate_ranks}",
                details={"duplicate_ranks": duplicate_ranks},
            )

        if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise JourneyValidationError(
                f"Strategy v{version} produced non-contiguous ranks "
                f"{sorted(ranks)}; expected 1..{len(ranks)}.",
                details={
                    "ranks": sorted(ranks),
                    "expected": list(range(1, len(ranks) + 1)),
                },
            )

    def _resolve_version(self, requested: Optional[str]) -> str:
        if requested is not None:
            return requested
        default = self._registry.default_version
        if default is None:
            raise JourneyMethodologyNotConfigured("(default)")
        return default


def _duplicates(values: Sequence[object]) -> List[object]:
    seen: set = set()
    duplicates: List[object] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


__all__ = ["JourneyRecommendationService"]
