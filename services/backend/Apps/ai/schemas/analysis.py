"""
Combined assessment-analysis wire contract.

``POST /internal/ai/v1/assessment/analyze`` runs the full pipeline
(validate → score → recommend) and returns one structured document, so this
response carries both the competency scores and the AI competency priorities.

This module lives apart from :mod:`app.schemas.assessment` and
:mod:`app.schemas.recommendation` because the latter already imports the
former; a combined model in either would create an import cycle.

``user_priority`` is absent by construction and, via ``extra="forbid"``,
cannot be introduced by a caller. Django owns it.
"""

from typing import Any, Dict, List

from pydantic import ConfigDict, Field, model_validator

from Apps.ai.schemas.assessment import CompetencyScore
from Apps.ai.schemas.common import (
    COMPETENCY_COUNT,
    ExternalRef,
    VersionedResponse,
    ensure_exact_count,
    ensure_priority_permutation,
    ensure_unique,
)
from Apps.ai.schemas.recommendation import CompetencyRecommendation


class AssessmentAnalysisResponse(VersionedResponse):
    """Full AI analysis result returned to Django for persistence.

    The example below illustrates the wire *shape* Django should integrate
    against. ``competency_1``..``competency_6`` are placeholder codes: the
    approved EQi-30 competency taxonomy has not been supplied to this
    service (see ``app/domain/competencies.py``), so no real code names are
    fabricated here. Real values populate this exact shape once an approved
    scoring/recommendation methodology is registered — until then this
    endpoint returns ``501`` (see the route's documented responses).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": "django-req-a1b2c3d4",
                    "user_ref": "django-user-48213",
                    "instrument_version": "eqi30-self-report-v1",
                    "scoring_version": "scoring-v1",
                    "recommendation_version": "recommendation-v1",
                    "competency_scores": [
                        {
                            "competency_code": "competency_1",
                            "score": 6.4,
                            "scale_min": 1.0,
                            "scale_max": 10.0,
                        },
                        {
                            "competency_code": "competency_2",
                            "score": 7.1,
                            "scale_min": 1.0,
                            "scale_max": 10.0,
                        },
                        {
                            "competency_code": "competency_3",
                            "score": 5.8,
                            "scale_min": 1.0,
                            "scale_max": 10.0,
                        },
                        {
                            "competency_code": "competency_4",
                            "score": 8.0,
                            "scale_min": 1.0,
                            "scale_max": 10.0,
                        },
                        {
                            "competency_code": "competency_5",
                            "score": 6.9,
                            "scale_min": 1.0,
                            "scale_max": 10.0,
                        },
                        {
                            "competency_code": "competency_6",
                            "score": 7.5,
                            "scale_min": 1.0,
                            "scale_max": 10.0,
                        },
                    ],
                    "recommendations": [
                        {
                            "competency_code": "competency_3",
                            "ai_priority": 1,
                            "rationale": (
                                "Lowest relative score; addressing it first "
                                "offers the most room for growth."
                            ),
                        },
                        {"competency_code": "competency_1", "ai_priority": 2},
                        {"competency_code": "competency_5", "ai_priority": 3},
                        {"competency_code": "competency_2", "ai_priority": 4},
                        {"competency_code": "competency_6", "ai_priority": 5},
                        {"competency_code": "competency_4", "ai_priority": 6},
                    ],
                    "validation_warnings": [],
                    "metadata": {
                        "scoring_strategy": "example-scoring-v1",
                        "recommendation_strategy": "example-recommendation-v1",
                    },
                }
            ]
        }
    )

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
        description="Scoring methodology version actually applied.",
    )
    recommendation_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Recommendation strategy version actually applied.",
    )
    competency_scores: List[CompetencyScore] = Field(
        default_factory=list,
        description="Per-competency scores. Competency codes must be unique.",
    )
    recommendations: List[CompetencyRecommendation] = Field(
        ...,
        description=(
            f"Exactly {COMPETENCY_COUNT} competency recommendations with unique "
            f"codes and ai_priority forming the permutation 1..{COMPETENCY_COUNT}."
        ),
    )
    validation_warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal validation notices raised during assessment intake.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for non-authoritative annotations.",
    )

    @model_validator(mode="after")
    def _validate_structure(self) -> "AssessmentAnalysisResponse":
        ensure_unique(
            [c.competency_code for c in self.competency_scores],
            label="competency_code",
        )
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


__all__ = ["AssessmentAnalysisResponse"]
