"""
Journey recommendation data contracts.

The user-selection taxonomy has NOT been supplied by the backend team, and
CLAUDE.md forbids inventing one. Rather than guessing field names and
allowed values, this module models the selection payload as a *versioned
envelope*:

    selection_schema_version  ->  which taxonomy the payload conforms to
    selections                ->  the payload itself, structurally open

When the real taxonomy arrives it is registered against its version and
validated by the resolution layer (Phase 7). The envelope shape does not
change, so the backend contract stays stable across that handover.

Likewise, journey structure, length and sequencing rules are not defined
here — only the shape of a ranked recommendation result.
"""

from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field, model_validator

from Apps.ai.schemas.common import (
    AIPriority,
    COMPETENCY_COUNT,
    CompetencyCode,
    ExternalRef,
    LocaleTag,
    StrictModel,
    VersionedRequest,
    VersionedResponse,
    ensure_exact_count,
    ensure_unique,
)


class JourneyCompetencyScore(StrictModel):
    """A competency result carrying its AI-assigned priority.

    This closes the loop with the assessment pipeline
    (:class:`app.schemas.analysis.AssessmentAnalysisResponse`): Django
    persists ``ai_priority`` from that response and sends it back here so the
    journey strategy can prioritise accordingly. ``score``/``scale_min``/
    ``scale_max`` are optional and echo the assessment result when available.

    ``user_priority`` is not accepted here — it is Django's alone.
    """

    competency_code: CompetencyCode = Field(
        ..., description="Opaque competency identifier from the backend taxonomy."
    )
    ai_priority: AIPriority = Field(
        ...,
        description=(
            f"AI-assigned priority, 1..{COMPETENCY_COUNT} where 1 is highest. "
            "Distinct from user_priority, which Django owns and does not send here."
        ),
    )
    score: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Competency score, echoed from the assessment result when available.",
    )
    scale_min: Optional[float] = Field(
        default=None, allow_inf_nan=False, description="Lower bound of the score scale."
    )
    scale_max: Optional[float] = Field(
        default=None, allow_inf_nan=False, description="Upper bound of the score scale."
    )

    @model_validator(mode="after")
    def _validate_scale(self) -> "JourneyCompetencyScore":
        if (
            self.scale_min is not None
            and self.scale_max is not None
            and self.scale_min >= self.scale_max
        ):
            raise ValueError("scale_min must be less than scale_max")
        return self


class JourneySelection(StrictModel):
    """Versioned envelope carrying the user's journey selections."""

    selection_schema_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Version of the user-selection taxonomy the payload conforms to. "
            "Required so an unknown taxonomy is rejected, never defaulted."
        ),
    )
    selections: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Selection payload. Intentionally open: the taxonomy is owned by "
            "the backend contract and validated against the registered schema "
            "version, not hardcoded here."
        ),
    )


class JourneyRecommendationRequest(VersionedRequest):
    """Request asking the AI service to recommend a journey.

    ``selections`` in the example below uses a clearly generic placeholder
    key: the approved user-selection taxonomy has not been supplied to this
    service (see ``app/domain/journey.py``), so no specific field names are
    fabricated here. Send whatever your approved selection schema defines.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_ref": "django-user-48213",
                    "competencies": [
                        {
                            "competency_code": "competency_1",
                            "ai_priority": 2,
                            "score": 6.4,
                        },
                        {
                            "competency_code": "competency_2",
                            "ai_priority": 4,
                            "score": 7.1,
                        },
                        {
                            "competency_code": "competency_3",
                            "ai_priority": 1,
                            "score": 5.8,
                        },
                        {
                            "competency_code": "competency_4",
                            "ai_priority": 6,
                            "score": 8.0,
                        },
                        {
                            "competency_code": "competency_5",
                            "ai_priority": 3,
                            "score": 6.9,
                        },
                        {
                            "competency_code": "competency_6",
                            "ai_priority": 5,
                            "score": 7.5,
                        },
                    ],
                    "selection": {
                        "selection_schema_version": "selection-v1",
                        "selections": {"example_selection_key": "example_value"},
                    },
                    "locale": "en-GB",
                    "request_id": "django-req-e5f6a7b8",
                }
            ]
        }
    )

    user_ref: ExternalRef = Field(
        ..., description="Opaque backend user reference, used only for correlation."
    )
    journey_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Requested journey recommendation strategy version.",
    )
    competencies: List[JourneyCompetencyScore] = Field(
        ...,
        description=(
            f"Competency results for exactly {COMPETENCY_COUNT} competencies, "
            "each carrying the ai_priority Django persisted from the "
            "assessment pipeline. Required so the journey strategy can "
            "prioritise which competencies to address."
        ),
    )
    selection: JourneySelection = Field(
        ..., description="Versioned user-selection envelope."
    )
    locale: Optional[LocaleTag] = Field(
        default=None, description="BCP-47 locale tag for generated content."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for backend-supplied assessment/other context.",
    )

    @model_validator(mode="after")
    def _validate_competencies(self) -> "JourneyRecommendationRequest":
        codes = [c.competency_code for c in self.competencies]
        ensure_exact_count(codes, expected=COMPETENCY_COUNT, label="competencies")
        ensure_unique(codes, label="competency_code")
        return self


class JourneyRecommendationItem(StrictModel):
    """A single ranked journey recommendation."""

    reference: ExternalRef = Field(
        ...,
        description=(
            "Opaque reference to the recommended journey/content item, resolved "
            "by the backend. The AI service does not define journey content."
        ),
    )
    rank: int = Field(
        ...,
        ge=1,
        description="1-based ordering position; 1 is the strongest recommendation.",
    )
    rationale: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional explanation derived from supplied inputs.",
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point pending the journey content contract.",
    )


class JourneyRecommendationResponse(VersionedResponse):
    """Ranked journey recommendations returned to Django for persistence."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": "django-req-e5f6a7b8",
                    "user_ref": "django-user-48213",
                    "journey_version": "journey-v1",
                    "selection_schema_version": "selection-v1",
                    "recommendations": [
                        {
                            "reference": "journey-item-001",
                            "rank": 1,
                            "rationale": (
                                "Addresses your highest-priority competency first."
                            ),
                        },
                        {"reference": "journey-item-014", "rank": 2},
                        {"reference": "journey-item-022", "rank": 3},
                    ],
                    "metadata": {"journey_strategy": "example-journey-v1"},
                }
            ]
        }
    )

    user_ref: ExternalRef = Field(
        ..., description="Correlation reference echoed from the request."
    )
    journey_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Journey recommendation strategy version actually applied.",
    )
    selection_schema_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Selection taxonomy version the request was resolved against.",
    )
    recommendations: List[JourneyRecommendationItem] = Field(
        default_factory=list,
        description="Ranked journey items. References and ranks must be unique.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for non-authoritative annotations.",
    )

    @model_validator(mode="after")
    def _validate_ranking(self) -> "JourneyRecommendationResponse":
        ensure_unique([r.reference for r in self.recommendations], label="reference")
        ranks = [r.rank for r in self.recommendations]
        ensure_unique(ranks, label="rank")
        if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError(
                f"ranks must be exactly 1..{len(ranks)} with no gaps; got {sorted(ranks)}"
            )
        return self

    def ordered(self) -> List[JourneyRecommendationItem]:
        """Return recommendations sorted by ``rank`` ascending."""
        return sorted(self.recommendations, key=lambda r: r.rank)


__all__ = [
    "JourneyCompetencyScore",
    "JourneySelection",
    "JourneyRecommendationRequest",
    "JourneyRecommendationItem",
    "JourneyRecommendationResponse",
]
