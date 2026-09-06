"""
Scoring domain models for the EQi-30 AI service.

This module defines the **domain-level abstractions** for scoring:

* ``ScoringStrategy`` — the plug-point for approved psychometric methodology.
* ``ScoringResult`` — the structured intermediate scoring output.
* ``ScoringConfig`` — version-aware scoring configuration.
* Error types specific to the scoring domain.

Pipeline position::

    AssessmentResult (from assessment domain)
         ↓
    ScoringService (orchestrator)
         ↓  delegates to
    ScoringStrategy.compute_scores()
         ↓  produces
    ScoringResult (domain value object)
         ↓  mapped to
    AssessmentResponse (wire schema)

Design rules (from CLAUDE.md):

* **No invented psychometrics** — this module defines the *interface*, never
  the methodology (formulas, weights, normalization, reverse scoring,
  thresholds).
* **Explicit failure** — when no approved methodology is configured, the
  service returns a clear structured error.  Scores are **never** fabricated.
* **Deterministic** — same input + same strategy version → identical output.
* **Pluggable** — a new methodology is added by implementing
  ``ScoringStrategy`` and registering it.  No route, schema, recommendation,
  journey, or chatbot code changes required.
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
# Exceptions
# ---------------------------------------------------------------------------


class ScoringError(AppException):
    """Base class for all scoring-related failures."""


class ScoringMethodologyNotConfigured(ScoringError):
    """No approved scoring methodology has been registered for the
    requested version."""

    def __init__(self, version: str):
        super().__init__(
            message=(
                f"No approved scoring methodology is configured for version "
                f"'{version}'. The AI service cannot fabricate scores. "
                f"Register the approved methodology before invoking scoring."
            ),
            code="SCORING_METHODOLOGY_NOT_CONFIGURED",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={"requested_version": version},
        )


class UnsupportedScoringVersion(ScoringError):
    """The requested scoring version is not recognized by the service."""

    def __init__(self, version: str, available: Sequence[str]):
        super().__init__(
            message=(
                f"Scoring version '{version}' is not supported. "
                f"Available versions: {list(available) if available else 'none'}."
            ),
            code="UNSUPPORTED_SCORING_VERSION",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={
                "requested_version": version,
                "available_versions": list(available),
            },
        )


class ScoringInputError(ScoringError):
    """The assessment input is structurally invalid for scoring."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            code="SCORING_INPUT_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


# ---------------------------------------------------------------------------
# Scoring status
# ---------------------------------------------------------------------------


class ScoringStatus(str, Enum):
    """Processing status of a scoring result."""

    SCORED = "scored"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------


class CompetencyScoreResult(BaseModel):
    """A single competency score produced by a scoring strategy.

    This is the domain representation — decoupled from the wire-contract
    ``CompetencyScore`` in ``app.schemas.assessment``.

    No scale is assumed.  ``scale_min`` / ``scale_max`` are reported by
    the scoring methodology so persisted scores remain interpretable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    competency_code: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Competency identifier.",
    )
    score: float = Field(
        ...,
        allow_inf_nan=False,
        description="Score produced by the approved methodology.",
    )
    scale_min: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Lower bound of the score scale.",
    )
    scale_max: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Upper bound of the score scale.",
    )
    ability_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Optional per-ability score breakdown.",
    )

    @model_validator(mode="after")
    def _validate_scale(self) -> "CompetencyScoreResult":
        if (
            self.scale_min is not None
            and self.scale_max is not None
            and self.scale_min >= self.scale_max
        ):
            raise ValueError("scale_min must be less than scale_max")
        return self


class ScoringResult(BaseModel):
    """Structured scoring output produced by the scoring pipeline.

    This is the domain-level result.  It is mapped to the wire-contract
    ``AssessmentResponse`` by the scoring service before returning to
    the API layer.
    """

    model_config = ConfigDict(extra="forbid")

    user_ref: str = Field(
        ..., description="Correlation reference echoed from the request.",
    )
    instrument_version: str = Field(
        ..., description="Instrument version the responses were scored against.",
    )
    scoring_version: str = Field(
        ..., description="Scoring methodology version actually applied.",
    )
    status: ScoringStatus = Field(
        default=ScoringStatus.SCORED,
        description="Processing status.",
    )
    competency_scores: List[CompetencyScoreResult] = Field(
        default_factory=list,
        description="Per-competency scores.  Empty when status != SCORED.",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Correlation ID from the originating request.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Strategy-supplied metadata (description, timing, etc.).",
    )
    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of scoring completion.",
    )

    @model_validator(mode="after")
    def _validate_unique_competencies(self) -> "ScoringResult":
        codes = [cs.competency_code for cs in self.competency_scores]
        seen: set[str] = set()
        duplicates: list[str] = []
        for code in codes:
            if code in seen and code not in duplicates:
                duplicates.append(code)
            seen.add(code)
        if duplicates:
            raise ValueError(
                f"Duplicate competency codes in scoring result: {duplicates}"
            )
        return self


# ---------------------------------------------------------------------------
# Scoring strategy (abstract interface)
# ---------------------------------------------------------------------------


class ScoringStrategy(abc.ABC):
    """Abstract base class for a versioned scoring methodology.

    Concrete implementations supply the approved psychometric logic.

    Implementors must:

    * Return a list of ``CompetencyScoreResult`` with real, methodology-
      derived values — never placeholder or fabricated scores.
    * Be deterministic: the same inputs produce the same result.
    * Raise ``ScoringInputError`` when inputs fail methodology-specific
      validation (e.g. unexpected item count, out-of-range values).

    The service will *not* auto-generate any subclass.  A concrete
    implementation is expected to be authored by a qualified psychometric
    professional and reviewed before registration.

    Adding a new methodology requires ONLY:

    1. Implement ``ScoringStrategy``.
    2. Register it via ``ScoringStrategyRegistry.register()``.

    No changes to routes, schemas, recommendation, journey, or chatbot.
    """

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Stable version identifier for this methodology (e.g. ``'1.0'``)."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of this scoring methodology."""
        ...

    @abc.abstractmethod
    def validate_input(
        self,
        answers: List[dict],
        instrument_version: str,
    ) -> None:
        """Validate assessment answers against methodology-specific rules.

        Each ``answer`` dict contains at minimum ``item_id`` and ``value``.
        Raise ``ScoringInputError`` on any violation.  The service calls
        this *before* ``compute_scores``.
        """
        ...

    @abc.abstractmethod
    def compute_scores(
        self,
        answers: List[dict],
        instrument_version: str,
    ) -> List[CompetencyScoreResult]:
        """Compute competency scores from validated assessment answers.

        This method is the single location where psychometric logic
        executes.  The implementation **must not fabricate** results.
        """
        ...


# ---------------------------------------------------------------------------
# Scoring configuration
# ---------------------------------------------------------------------------


class ScoringConfig(BaseModel):
    """Metadata about a registered scoring strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(..., description="Strategy version identifier.")
    description: str = Field(..., description="Human-readable description.")
    is_default: bool = Field(
        default=False,
        description="Whether this is the default scoring version.",
    )


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------


class ScoringStrategyRegistry:
    """Registry mapping version strings to strategy instances.

    Only one instance lives in the service (see ``get_scoring_registry``).
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, ScoringStrategy] = {}
        self._default_version: Optional[str] = None

    def register(
        self,
        strategy: ScoringStrategy,
        *,
        set_default: bool = False,
    ) -> None:
        """Register a scoring strategy under its declared version."""
        version = strategy.version
        self._strategies[version] = strategy
        if set_default or self._default_version is None:
            self._default_version = version

    def get(self, version: str) -> ScoringStrategy:
        """Retrieve a registered strategy or raise ``UnsupportedScoringVersion``."""
        try:
            return self._strategies[version]
        except KeyError:
            raise UnsupportedScoringVersion(
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

    def get_config(self) -> List[ScoringConfig]:
        """Return metadata about all registered strategies."""
        return [
            ScoringConfig(
                version=s.version,
                description=s.description,
                is_default=(s.version == self._default_version),
            )
            for s in self._strategies.values()
        ]

    def clear(self) -> None:
        """Remove all registered strategies.  Intended for testing only."""
        self._strategies.clear()
        self._default_version = None


# Module-level singleton
_registry = ScoringStrategyRegistry()


def get_scoring_registry() -> ScoringStrategyRegistry:
    """Return the singleton scoring strategy registry."""
    return _registry


__all__ = [
    "ScoringError",
    "ScoringMethodologyNotConfigured",
    "UnsupportedScoringVersion",
    "ScoringInputError",
    "ScoringStatus",
    "CompetencyScoreResult",
    "ScoringResult",
    "ScoringStrategy",
    "ScoringConfig",
    "ScoringStrategyRegistry",
    "get_scoring_registry",
]
