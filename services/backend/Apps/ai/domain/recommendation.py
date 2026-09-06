"""
Recommendation domain models for the EQi-30 AI service.

This module defines the **domain-level abstractions** for competency
recommendation:

* ``RecommendationStrategy`` — the plug-point for ranking methodology.
* ``RecommendationResult`` — structured intermediate recommendation output.
* ``CompetencyRecommendationItem`` — a single ranked competency.
* ``RecommendationStrategyRegistry`` — versioned registry.

Pipeline position::

    ScoringResult (from scoring domain)
         ↓
    RecommendationService (orchestrator)
         ↓  delegates to
    RecommendationStrategy.rank()
         ↓  produces
    RecommendationResult (domain)
         ↓  mapped to
    CompetencyRecommendationResponse (wire schema)

Design rules (from CLAUDE.md):

* **ai_priority only** — the AI service produces ``ai_priority``.
  ``user_priority`` is owned by Django and must never appear in AI output.
* **No invented ranking logic** — this module defines the *interface*, never
  the ranking methodology.  When no methodology is configured the service
  returns a clear error.
* **Exactly 6 competencies** — input and output always carry all six
  competencies.  Priorities form the permutation 1..6 with no gaps or
  duplicates.
* **Deterministic** — same input + same strategy version → identical output.
* **Pluggable** — a new methodology is added by implementing
  ``RecommendationStrategy`` and registering it.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rest_framework import status

from Apps.ai.core.exceptions import AppException


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPETENCY_COUNT = 6


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RecommendationError(AppException):
    """Base class for all recommendation-related failures."""


class RecommendationMethodologyNotConfigured(RecommendationError):
    """No approved recommendation methodology is registered for the
    requested version."""

    def __init__(self, version: str):
        super().__init__(
            message=(
                f"No approved recommendation methodology is configured for "
                f"version '{version}'. The AI service cannot fabricate "
                f"priority rankings. Register the approved methodology "
                f"before invoking recommendation."
            ),
            code="RECOMMENDATION_METHODOLOGY_NOT_CONFIGURED",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={"requested_version": version},
        )


class UnsupportedRecommendationVersion(RecommendationError):
    """The requested recommendation version is not recognized."""

    def __init__(self, version: str, available: Sequence[str]):
        super().__init__(
            message=(
                f"Recommendation version '{version}' is not supported. "
                f"Available versions: {list(available) if available else 'none'}."
            ),
            code="UNSUPPORTED_RECOMMENDATION_VERSION",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={
                "requested_version": version,
                "available_versions": list(available),
            },
        )


class RecommendationInputError(RecommendationError):
    """The input to the recommendation service is invalid."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="RECOMMENDATION_INPUT_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class RecommendationValidationError(RecommendationError):
    """The recommendation output fails validation."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="RECOMMENDATION_VALIDATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------


class RecommendationStatus(str, Enum):
    """Processing status of a recommendation result."""

    RECOMMENDED = "recommended"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


class CompetencyScoreInput(BaseModel):
    """A competency score supplied as input to the recommendation strategy.

    This is a domain-internal representation — decoupled from both the
    scoring domain's ``CompetencyScoreResult`` and the wire schema's
    ``CompetencyScore``.
    """

    # ``str_strip_whitespace`` keeps this model as strict as the wire
    # ``CompetencyCode`` type, which already rejects whitespace-only codes.
    # Without it, "   " passes ``min_length=1`` and a blank identifier can
    # enter the domain from a strategy or internal caller.
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    competency_code: str = Field(
        ..., min_length=1, max_length=64,
        description="Competency identifier.",
    )
    score: Optional[float] = Field(
        default=None, allow_inf_nan=False,
        description="Score (None when scoring methodology is unavailable).",
    )
    scale_min: Optional[float] = Field(
        default=None, allow_inf_nan=False,
    )
    scale_max: Optional[float] = Field(
        default=None, allow_inf_nan=False,
    )


class CompetencyRecommendationItem(BaseModel):
    """A single competency with its AI-assigned priority.

    ``user_priority`` does not exist in this model.  Django owns it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    competency_code: str = Field(
        ..., min_length=1, max_length=64,
        description="Competency identifier.",
    )
    ai_priority: int = Field(
        ..., ge=1, le=COMPETENCY_COUNT,
        description=f"AI-assigned priority 1..{COMPETENCY_COUNT} (1 = highest).",
    )
    score: Optional[float] = Field(
        default=None, allow_inf_nan=False,
        description="Competency score echoed for convenience.",
    )
    rationale: Optional[str] = Field(
        default=None, max_length=2000,
        description="Optional explanation for this ranking.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point.",
    )


class RecommendationResult(BaseModel):
    """Structured recommendation output produced by the recommendation
    pipeline.

    Mapped to ``CompetencyRecommendationResponse`` before returning to
    the API layer.
    """

    model_config = ConfigDict(extra="forbid")

    user_ref: str = Field(
        ..., description="Correlation reference.",
    )
    recommendation_version: str = Field(
        ..., description="Recommendation strategy version actually applied.",
    )
    status: RecommendationStatus = Field(
        default=RecommendationStatus.RECOMMENDED,
    )
    recommendations: List[CompetencyRecommendationItem] = Field(
        ...,
        description=f"Exactly {COMPETENCY_COUNT} ranked competencies.",
    )
    request_id: Optional[str] = Field(
        default=None, description="Correlation ID.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
    )
    recommended_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _validate_recommendations(self) -> "RecommendationResult":
        if len(self.recommendations) != COMPETENCY_COUNT:
            raise ValueError(
                f"Expected exactly {COMPETENCY_COUNT} recommendations, "
                f"got {len(self.recommendations)}"
            )

        codes = [r.competency_code for r in self.recommendations]
        seen: set[str] = set()
        dup_codes: list[str] = []
        for c in codes:
            if c in seen and c not in dup_codes:
                dup_codes.append(c)
            seen.add(c)
        if dup_codes:
            raise ValueError(f"Duplicate competency codes: {dup_codes}")

        priorities = [r.ai_priority for r in self.recommendations]
        seen_p: set[int] = set()
        dup_p: list[int] = []
        for p in priorities:
            if p in seen_p and p not in dup_p:
                dup_p.append(p)
            seen_p.add(p)
        if dup_p:
            raise ValueError(f"Duplicate ai_priority values: {dup_p}")

        if sorted(priorities) != list(range(1, COMPETENCY_COUNT + 1)):
            raise ValueError(
                f"ai_priority must be exactly 1..{COMPETENCY_COUNT}; "
                f"got {sorted(priorities)}"
            )

        return self

    def ordered(self) -> List[CompetencyRecommendationItem]:
        """Return recommendations sorted by ai_priority ascending."""
        return sorted(self.recommendations, key=lambda r: r.ai_priority)


# ---------------------------------------------------------------------------
# Recommendation strategy (abstract interface)
# ---------------------------------------------------------------------------


class RecommendationStrategy(abc.ABC):
    """Abstract base class for a versioned recommendation methodology.

    Concrete implementations supply the approved ranking logic that
    transforms competency scores into a prioritised list.

    Implementors must:

    * Return exactly ``COMPETENCY_COUNT`` (6) ``CompetencyRecommendationItem``
      objects with valid, non-duplicated ``ai_priority`` values 1..6.
    * Be deterministic: same inputs → same output.
    * Raise ``RecommendationInputError`` for invalid input.
    * **Never** include or reference ``user_priority``.

    Adding a new methodology requires ONLY:

    1. Implement ``RecommendationStrategy``.
    2. Register it via ``RecommendationStrategyRegistry.register()``.

    No changes to routes, schemas, scoring, journey, or chatbot.
    """

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Stable version identifier."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @abc.abstractmethod
    def validate_input(
        self,
        scores: List[CompetencyScoreInput],
        context: Dict[str, Any],
    ) -> None:
        """Validate input against methodology-specific rules.

        Raise ``RecommendationInputError`` on any violation.
        """
        ...

    @abc.abstractmethod
    def rank(
        self,
        scores: List[CompetencyScoreInput],
        context: Dict[str, Any],
    ) -> List[CompetencyRecommendationItem]:
        """Rank competencies and assign ``ai_priority`` 1..6.

        Must return exactly ``COMPETENCY_COUNT`` items.
        """
        ...


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------


class RecommendationStrategyRegistry:
    """Versioned registry mapping version strings to strategy instances."""

    def __init__(self) -> None:
        self._strategies: Dict[str, RecommendationStrategy] = {}
        self._default_version: Optional[str] = None

    def register(
        self,
        strategy: RecommendationStrategy,
        *,
        set_default: bool = False,
    ) -> None:
        self._strategies[strategy.version] = strategy
        if set_default or self._default_version is None:
            self._default_version = strategy.version

    def get(self, version: str) -> RecommendationStrategy:
        try:
            return self._strategies[version]
        except KeyError:
            raise UnsupportedRecommendationVersion(
                version, available=list(self._strategies.keys())
            )

    @property
    def default_version(self) -> Optional[str]:
        return self._default_version

    @property
    def available_versions(self) -> List[str]:
        return list(self._strategies.keys())

    @property
    def is_empty(self) -> bool:
        return len(self._strategies) == 0

    def clear(self) -> None:
        self._strategies.clear()
        self._default_version = None


# Module-level singleton
_registry = RecommendationStrategyRegistry()


def get_recommendation_registry() -> RecommendationStrategyRegistry:
    """Return the singleton recommendation strategy registry."""
    return _registry


__all__ = [
    "COMPETENCY_COUNT",
    "RecommendationError",
    "RecommendationMethodologyNotConfigured",
    "UnsupportedRecommendationVersion",
    "RecommendationInputError",
    "RecommendationValidationError",
    "RecommendationStatus",
    "CompetencyScoreInput",
    "CompetencyRecommendationItem",
    "RecommendationResult",
    "RecommendationStrategy",
    "RecommendationStrategyRegistry",
    "get_recommendation_registry",
]
