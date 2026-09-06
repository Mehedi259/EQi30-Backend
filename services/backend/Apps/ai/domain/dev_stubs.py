"""
Development stub strategies for local testing and demonstration.

These strategies are registered automatically during application startup in
development mode (`ENVIRONMENT="development"` or `DEBUG=true`) so that local
developers can test all endpoints in Swagger UI (`/docs`) and receive
structured `HTTP 200 OK` responses instead of `501 Not Implemented`.
"""

from typing import Any, Dict, List

from Apps.ai.domain.journey import (
    JourneyItem,
    JourneyRecommendationInput,
    JourneyRecommendationResult,
    JourneyRecommendationStrategy,
    JourneySelectionEnvelope,
    JourneyStatus,
    get_journey_registry,
)
from Apps.ai.domain.recommendation import (
    CompetencyRecommendationItem,
    CompetencyScoreInput,
    RecommendationResult,
    RecommendationStatus,
    RecommendationStrategy,
    get_recommendation_registry,
)
from Apps.ai.domain.scoring import (
    CompetencyScoreResult,
    ScoringResult,
    ScoringStatus,
    ScoringStrategy,
    get_scoring_registry,
)


class DevScoringStrategy(ScoringStrategy):
    """Development stub scoring strategy."""

    @property
    def version(self) -> str:
        return "scoring-v1"

    @property
    def description(self) -> str:
        return "Development stub scoring strategy for local API testing."

    def validate_input(
        self, answers: List[dict], instrument_version: str
    ) -> None:
        pass

    def compute_scores(
        self, answers: List[dict], instrument_version: str
    ) -> List[CompetencyScoreResult]:
        mean_val = (
            sum(a.get("value", 5.0) for a in answers) / len(answers)
            if answers
            else 5.0
        )
        return [
            CompetencyScoreResult(
                competency_code=f"competency_{i+1}",
                score=round(min(10.0, max(1.0, mean_val + (i * 0.5 - 1.2))), 1),
                scale_min=1.0,
                scale_max=10.0,
            )
            for i in range(6)
        ]


class DevRecommendationStrategy(RecommendationStrategy):
    """Development stub recommendation strategy."""

    @property
    def version(self) -> str:
        return "recommendation-v1"

    @property
    def description(self) -> str:
        return "Development stub recommendation strategy for local API testing."

    def validate_input(
        self, scores: List[CompetencyScoreInput], context: Dict[str, Any]
    ) -> None:
        pass

    def rank(
        self, scores: List[CompetencyScoreInput], context: Dict[str, Any]
    ) -> List[CompetencyRecommendationItem]:
        sorted_scores = sorted(
            scores, key=lambda s: s.score if s.score is not None else 0.0
        )
        items = []
        for rank, s in enumerate(sorted_scores, 1):
            items.append(
                CompetencyRecommendationItem(
                    competency_code=s.competency_code,
                    ai_priority=rank,
                    score=s.score,
                    rationale=f"Assigned priority #{rank} based on relative assessment score.",
                )
            )
        return items


class DevJourneyStrategy(JourneyRecommendationStrategy):
    """Development stub journey strategy."""

    @property
    def version(self) -> str:
        return "journey-v1"

    @property
    def description(self) -> str:
        return "Development stub journey strategy for local API testing."

    def validate_input(self, input_data: JourneyRecommendationInput) -> None:
        pass

    def generate(
        self, input_data: JourneyRecommendationInput
    ) -> List[JourneyItem]:
        return [
            JourneyItem(
                reference="journey-item-001",
                rank=1,
                rationale="Addresses your highest-priority growth competency first.",
            ),
            JourneyItem(
                reference="journey-item-014",
                rank=2,
                rationale="Builds foundational emotional resilience habits.",
            ),
            JourneyItem(
                reference="journey-item-022",
                rank=3,
                rationale="Advanced interpersonal communication practice.",
            ),
        ]


def register_dev_stubs() -> None:
    """Register development stubs into the global strategy registries."""
    scoring_reg = get_scoring_registry()
    rec_reg = get_recommendation_registry()
    journey_reg = get_journey_registry()

    dev_scoring = DevScoringStrategy()
    dev_rec = DevRecommendationStrategy()
    dev_journey = DevJourneyStrategy()

    scoring_reg.register(dev_scoring, set_default=True)
    rec_reg.register(dev_rec, set_default=True)
    journey_reg.register(dev_journey, set_default=True)


__all__ = ["register_dev_stubs"]
