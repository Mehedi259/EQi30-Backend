"""
Competency recommendation data contracts.

Validation rules enforced here:

* exactly ``COMPETENCY_COUNT`` (6) competency recommendations
* competency codes are unique
* ``ai_priority`` values form exactly the permutation 1..6 — no gaps,
  no duplicates, nothing out of range

``ai_priority`` vs ``user_priority``
------------------------------------
The AI service produces ``ai_priority`` only. ``user_priority`` is owned and
persisted exclusively by Django. These are distinct values and must never be
conflated, so ``user_priority`` appears in no model in this module — and
because every model inherits ``extra="forbid"``, a caller that tries to send
one gets a validation error rather than having it silently ignored.

No ranking rule is implemented here. This module validates the *shape* of a
recommendation; the logic that decides priorities arrives with the backend
methodology (Phase 7).
"""

from typing import Any, Dict, List, Optional

from pydantic import Field, model_validator

from Apps.ai.schemas.common import (
    COMPETENCY_COUNT,
    AIPriority,
    CompetencyCode,
    ExternalRef,
    StrictModel,
    VersionedRequest,
    VersionedResponse,
    ensure_exact_count,
    ensure_priority_permutation,
    ensure_unique,
)
from Apps.ai.schemas.assessment import CompetencyScore


class CompetencyRecommendation(StrictModel):
    """A single competency ranked by the AI service."""

    competency_code: CompetencyCode = Field(
        ..., description="Opaque competency identifier from the backend taxonomy."
    )
    ai_priority: AIPriority = Field(
        ...,
        description=(
            f"AI-assigned priority, 1..{COMPETENCY_COUNT} where 1 is highest. "
            "Distinct from user_priority, which Django owns."
        ),
    )
    rationale: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional explanation derived from supplied inputs.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for non-authoritative annotations.",
    )


class CompetencyRecommendationRequest(VersionedRequest):
    """Request asking the AI service to prioritise competencies."""

    user_ref: ExternalRef = Field(
        ..., description="Opaque backend user reference, used only for correlation."
    )
    recommendation_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Requested recommendation strategy version.",
    )
    competency_scores: List[CompetencyScore] = Field(
        ...,
        description=(
            f"Assessment scores for exactly {COMPETENCY_COUNT} competencies, "
            "supplied by Django."
        ),
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for backend-supplied context.",
    )

    @model_validator(mode="after")
    def _validate_competencies(self) -> "CompetencyRecommendationRequest":
        codes = [c.competency_code for c in self.competency_scores]
        ensure_exact_count(codes, expected=COMPETENCY_COUNT, label="competency_scores")
        ensure_unique(codes, label="competency_code")
        return self


class CompetencyRecommendationResponse(VersionedResponse):
    """Prioritised competency list returned to Django for persistence."""

    user_ref: ExternalRef = Field(
        ..., description="Correlation reference echoed from the request."
    )
    recommendation_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Recommendation strategy version actually applied.",
    )
    recommendations: List[CompetencyRecommendation] = Field(
        ...,
        description=(
            f"Exactly {COMPETENCY_COUNT} recommendations with unique competency "
            f"codes and ai_priority values forming the permutation 1..{COMPETENCY_COUNT}."
        ),
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for non-authoritative annotations.",
    )

    @model_validator(mode="after")
    def _validate_recommendations(self) -> "CompetencyRecommendationResponse":
        ensure_exact_count(
            self.recommendations, expected=COMPETENCY_COUNT, label="recommendations"
        )
        ensure_unique(
            [r.competency_code for r in self.recommendations], label="competency_code"
        )
        ensure_priority_permutation(
            [r.ai_priority for r in self.recommendations], expected=COMPETENCY_COUNT
        )
        return self

    def ordered(self) -> List[CompetencyRecommendation]:
        """Return recommendations sorted by ``ai_priority`` ascending."""
        return sorted(self.recommendations, key=lambda r: r.ai_priority)


__all__ = [
    "CompetencyRecommendation",
    "CompetencyRecommendationRequest",
    "CompetencyRecommendationResponse",
]
