"""
Assessment data contracts.

Scope boundary — what these schemas deliberately do NOT do:

* They do not define the response scale. Item value bounds belong to the
  versioned assessment instrument, which the backend has not supplied; the
  schema therefore accepts any finite number and defers range checking to
  the scoring layer (Phase 5).
* They do not define scoring. No aggregation, weighting, normalization,
  reverse scoring or banding is expressed or implied here.
* ``CompetencyScore.score`` is optional precisely because the scoring
  methodology is not yet available. A missing score is represented as
  ``None`` and never as a fabricated placeholder value.
"""

from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field, model_validator

from Apps.ai.schemas.common import (
    CompetencyCode,
    ExternalRef,
    StrictModel,
    VersionedRequest,
    VersionedResponse,
    ensure_unique,
)


class AssessmentItemResponse(StrictModel):
    """A single answer submitted by the user for one assessment item."""

    item_id: ExternalRef = Field(
        ...,
        description="Opaque assessment item identifier defined by the instrument.",
    )
    value: float = Field(
        ...,
        allow_inf_nan=False,
        description=(
            "Raw response value. The valid range is declared by the assessment "
            "instrument version, not by this schema."
        ),
    )


class AssessmentRequest(VersionedRequest):
    """Assessment payload sent by Django for AI processing."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_ref": "django-user-48213",
                    "instrument_version": "eqi30-self-report-v1",
                    "responses": [
                        {"item_id": "sm_01", "value": 7},
                        {"item_id": "sm_02", "value": 5},
                        {"item_id": "ip_01", "value": 8},
                        {"item_id": "st_01", "value": 4},
                    ],
                    "request_id": "django-req-a1b2c3d4",
                }
            ]
        }
    )

    user_ref: ExternalRef = Field(
        ...,
        description=(
            "Opaque, backend-issued user reference used only for correlation. "
            "The AI service never persists it."
        ),
    )
    instrument_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Version of the assessment instrument the responses belong to.",
    )
    scoring_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "Requested scoring methodology version. When omitted the service "
            "resolves its configured default."
        ),
    )
    responses: List[AssessmentItemResponse] = Field(
        ...,
        min_length=1,
        description="Submitted item responses. Must contain at least one entry.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for backend-supplied context.",
    )

    @model_validator(mode="after")
    def _validate_unique_items(self) -> "AssessmentRequest":
        ensure_unique([r.item_id for r in self.responses], label="item_id")
        return self


class CompetencyScore(StrictModel):
    """A score produced for one competency.

    No scale is assumed. ``scale_min``/``scale_max`` are reported by the
    scoring methodology when it is available so that a persisted score
    remains interpretable later.
    """

    competency_code: CompetencyCode = Field(
        ..., description="Opaque competency identifier from the backend taxonomy."
    )
    score: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description=(
            "Score produced by the pluggable scoring strategy. Null when the "
            "scoring methodology is unavailable — never a placeholder value."
        ),
    )
    scale_min: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Lower bound of the score scale, declared by the methodology.",
    )
    scale_max: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Upper bound of the score scale, declared by the methodology.",
    )
    ability_scores: Dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Optional per-ability breakdown keyed by opaque ability reference. "
            "Ability cardinality is defined by the backend taxonomy, not here."
        ),
    )

    @model_validator(mode="after")
    def _validate_scale(self) -> "CompetencyScore":
        if (
            self.scale_min is not None
            and self.scale_max is not None
            and self.scale_min >= self.scale_max
        ):
            raise ValueError("scale_min must be less than scale_max")
        return self


class AssessmentResponse(VersionedResponse):
    """AI assessment result returned to Django for persistence."""

    user_ref: ExternalRef = Field(
        ..., description="Correlation reference echoed from the request."
    )
    instrument_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Instrument version the responses were interpreted against.",
    )
    scoring_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Scoring methodology version actually applied. Persisted by Django "
            "so historical results stay reproducible."
        ),
    )
    competency_scores: List[CompetencyScore] = Field(
        default_factory=list,
        description="Per-competency scores. Competency codes must be unique.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for non-authoritative AI annotations.",
    )

    @model_validator(mode="after")
    def _validate_unique_competencies(self) -> "AssessmentResponse":
        ensure_unique(
            [c.competency_code for c in self.competency_scores],
            label="competency_code",
        )
        return self


__all__ = [
    "AssessmentItemResponse",
    "AssessmentRequest",
    "CompetencyScore",
    "AssessmentResponse",
]
