"""
Journey recommendation domain models for the EQi-30 AI service.

This module defines the **domain-level abstractions** for journey
recommendation:

* ``JourneyRecommendationStrategy`` — the plug-point for journey methodology.
* ``JourneyRecommendationResult`` — structured recommendation output.
* ``JourneyItem`` — a single ranked journey element.
* ``JourneyRecommendationInput`` — validated service input.
* ``JourneySelectionEnvelope`` — versioned user-selection carrier.
* ``JourneyStrategyRegistry`` / ``SelectionSchemaRegistry`` — versioned registries.

Pipeline position::

    RecommendationResult (ai_priority per competency)
         ↓
    JourneyRecommendationService (orchestrator)
         ↓  delegates to
    JourneyRecommendationStrategy.generate()
         ↓  produces
    JourneyRecommendationResult (domain)
         ↓  mapped to
    JourneyRecommendationResponse (wire schema)  ← Django persists

Design rules (from CLAUDE.md):

* **No invented user-selection taxonomy.** Selections travel inside a
  versioned envelope whose payload is structurally open. A selection schema
  is *registered*, never hardcoded. Until one is registered the envelope is
  accepted with a warning; once any schema is registered, unknown versions
  are rejected rather than silently defaulted.
* **No invented journey methodology.** This module defines the *interface*.
  With no strategy registered the service raises rather than fabricating.
* **ai_priority only.** ``user_priority`` appears nowhere and cannot be set.
* **Stateless.** Every object here is an in-memory value object. Nothing in
  this module reads, writes or persists anything. Django owns persistence.
* **Deterministic** — same input + same strategy version → identical output.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

from rest_framework import status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from Apps.ai.core.exceptions import AppException
from Apps.ai.domain.competencies import COMPETENCY_COUNT


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class JourneyError(AppException):
    """Base class for all journey-recommendation failures."""


class JourneyMethodologyNotConfigured(JourneyError):
    """No approved journey methodology is registered for the requested version."""

    def __init__(self, version: str):
        super().__init__(
            message=(
                f"No approved journey recommendation methodology is configured "
                f"for version '{version}'. The AI service cannot fabricate a "
                f"journey. Register the approved methodology before invoking "
                f"journey recommendation."
            ),
            code="JOURNEY_METHODOLOGY_NOT_CONFIGURED",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={"requested_version": version},
        )


class UnsupportedJourneyVersion(JourneyError):
    """The requested journey recommendation version is not recognized."""

    def __init__(self, version: str, available: Sequence[str]):
        super().__init__(
            message=(
                f"Journey recommendation version '{version}' is not supported. "
                f"Available versions: {list(available) if available else 'none'}."
            ),
            code="UNSUPPORTED_JOURNEY_VERSION",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={
                "requested_version": version,
                "available_versions": list(available),
            },
        )


class UnsupportedSelectionSchemaVersion(JourneyError):
    """The supplied user-selection schema version is not registered."""

    def __init__(self, version: str, available: Sequence[str]):
        super().__init__(
            message=(
                f"User-selection schema version '{version}' is not supported. "
                f"Available versions: {list(available) if available else 'none'}."
            ),
            code="UNSUPPORTED_SELECTION_SCHEMA_VERSION",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={
                "requested_version": version,
                "available_versions": list(available),
            },
        )


class JourneyInputError(JourneyError):
    """The input to the journey recommendation service is invalid."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="JOURNEY_INPUT_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class JourneyValidationError(JourneyError):
    """The journey recommendation output fails structural validation."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="JOURNEY_VALIDATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------


class JourneyStatus(str, Enum):
    """Processing status of a journey recommendation result."""

    RECOMMENDED = "recommended"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


class JourneySelectionEnvelope(BaseModel):
    """Versioned carrier for approved user selections/preferences.

    The taxonomy is **not** defined here. ``selections`` is structurally open
    and is validated against the schema registered under
    ``selection_schema_version`` — so the approved taxonomy arrives as
    registered data, never as invented field names or values.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    selection_schema_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Version of the user-selection taxonomy this payload conforms to.",
    )
    selections: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Approved user selections/preferences. Intentionally open pending "
            "the finalized taxonomy."
        ),
    )


class JourneyCompetencyInput(BaseModel):
    """One competency result carrying its AI-assigned priority.

    ``user_priority`` does not exist on this model. Django owns it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    competency_code: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Competency identifier.",
    )
    ai_priority: int = Field(
        ...,
        ge=1,
        le=COMPETENCY_COUNT,
        description=f"AI-assigned priority 1..{COMPETENCY_COUNT} (1 = highest).",
    )
    score: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Competency score (None when scoring methodology is unavailable).",
    )
    scale_min: Optional[float] = Field(default=None, allow_inf_nan=False)
    scale_max: Optional[float] = Field(default=None, allow_inf_nan=False)


class JourneyRecommendationInput(BaseModel):
    """Validated input to the journey recommendation service."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    user_ref: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Opaque backend user reference, used only for correlation.",
    )
    competencies: List[JourneyCompetencyInput] = Field(
        ...,
        description=(
            f"Exactly {COMPETENCY_COUNT} competency results with unique codes "
            f"and ai_priority forming the permutation 1..{COMPETENCY_COUNT}."
        ),
    )
    selection: JourneySelectionEnvelope = Field(
        ..., description="Versioned user-selection envelope."
    )
    locale: Optional[str] = Field(
        default=None,
        max_length=35,
        description="BCP-47 locale tag for generated content.",
    )
    journey_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Requested journey strategy version; None resolves the default.",
    )
    assessment_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for backend-supplied assessment context.",
    )
    request_id: Optional[str] = Field(default=None, max_length=128)

    @property
    def competency_codes(self) -> List[str]:
        return [c.competency_code for c in self.competencies]

    def ordered_competencies(self) -> List[JourneyCompetencyInput]:
        """Competencies sorted by ``ai_priority`` ascending (1 first)."""
        return sorted(self.competencies, key=lambda c: c.ai_priority)


class JourneyItem(BaseModel):
    """A single ranked journey element produced by a strategy.

    ``reference`` is opaque: the AI service does not define journey content,
    it recommends references the backend resolves.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reference: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Opaque reference to the recommended journey/content item.",
    )
    rank: int = Field(
        ..., ge=1, description="1-based ordering position; 1 is strongest."
    )
    competency_code: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Competency this item addresses, when applicable.",
    )
    rationale: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Explanation derived from supplied inputs.",
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point pending the journey content contract.",
    )


class JourneyRecommendationResult(BaseModel):
    """Structured journey recommendation output.

    A pure in-memory value object. Producing one persists nothing; Django
    receives it and owns all storage.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_ref: str = Field(..., min_length=1, max_length=128)
    journey_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Journey strategy version actually applied. Preserved verbatim.",
    )
    selection_schema_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Selection taxonomy version the input was resolved against.",
    )
    status: JourneyStatus = Field(default=JourneyStatus.RECOMMENDED)
    items: List[JourneyItem] = Field(default_factory=list)
    locale: Optional[str] = Field(default=None, max_length=35)
    request_id: Optional[str] = Field(default=None, max_length=128)
    validation_warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of journey generation.",
    )

    @model_validator(mode="after")
    def _validate_items(self) -> "JourneyRecommendationResult":
        references = [item.reference for item in self.items]
        duplicates = _duplicates(references)
        if duplicates:
            raise ValueError(f"Duplicate journey references: {duplicates}")

        ranks = [item.rank for item in self.items]
        rank_duplicates = _duplicates(ranks)
        if rank_duplicates:
            raise ValueError(f"Duplicate journey ranks: {rank_duplicates}")

        if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError(
                f"Journey ranks must be exactly 1..{len(ranks)} with no gaps; "
                f"got {sorted(ranks)}"
            )
        return self

    def ordered(self) -> List[JourneyItem]:
        """Return items sorted by ``rank`` ascending."""
        return sorted(self.items, key=lambda item: item.rank)


def _duplicates(values: Sequence[Any]) -> List[Any]:
    seen: set = set()
    duplicates: List[Any] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class JourneyRecommendationStrategy(abc.ABC):
    """Abstract base class for a versioned journey recommendation methodology.

    Concrete implementations supply the approved journey-construction logic.

    Implementors must:

    * Return ``JourneyItem`` objects with contiguous ranks starting at 1.
    * Be deterministic: same input → same output.
    * Raise ``JourneyInputError`` when input fails methodology-specific rules.
    * **Never** reference or produce ``user_priority``.
    * **Never** persist anything — strategies are pure functions.

    Adding a methodology requires ONLY implementing this class and
    registering it. No changes to routes, schemas or services.
    """

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Stable version identifier for this methodology."""
        ...

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of this journey methodology."""
        ...

    @abc.abstractmethod
    def validate_input(self, journey_input: JourneyRecommendationInput) -> None:
        """Validate input against methodology-specific rules.

        Raise ``JourneyInputError`` on any violation. Called before
        ``generate``.
        """
        ...

    @abc.abstractmethod
    def generate(
        self, journey_input: JourneyRecommendationInput
    ) -> List[JourneyItem]:
        """Produce the ranked journey.

        This is the single location where journey methodology executes. It
        **must not fabricate** content when inputs are insufficient.
        """
        ...


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------


class JourneyStrategyRegistry:
    """Versioned registry mapping version strings to journey strategies."""

    def __init__(self) -> None:
        self._strategies: Dict[str, JourneyRecommendationStrategy] = {}
        self._default_version: Optional[str] = None

    def register(
        self,
        strategy: JourneyRecommendationStrategy,
        *,
        set_default: bool = False,
    ) -> None:
        self._strategies[strategy.version] = strategy
        if set_default or self._default_version is None:
            self._default_version = strategy.version

    def get(self, version: str) -> JourneyRecommendationStrategy:
        try:
            return self._strategies[version]
        except KeyError:
            raise UnsupportedJourneyVersion(
                version, available=list(self._strategies.keys())
            ) from None

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
        """Remove all registered strategies. Intended for testing only."""
        self._strategies.clear()
        self._default_version = None


#: A selection validator receives the raw selections payload and raises
#: ``JourneyInputError`` if it does not conform to the registered taxonomy.
SelectionValidator = Callable[[Dict[str, Any]], None]


class SelectionSchemaRegistry:
    """Registry of approved user-selection taxonomy versions.

    The taxonomy is not finalized, so no schema ships registered. While the
    registry is empty the service accepts any envelope and records a warning.
    Once any schema is registered, unknown versions are rejected — the
    taxonomy becomes enforceable without a code change.
    """

    def __init__(self) -> None:
        self._validators: Dict[str, Optional[SelectionValidator]] = {}

    def register(
        self,
        version: str,
        validator: Optional[SelectionValidator] = None,
    ) -> None:
        """Register an approved selection schema version.

        ``validator`` is optional: registering a version without one declares
        the version acceptable while leaving payload validation open.
        """
        self._validators[version] = validator

    def validate(self, envelope: JourneySelectionEnvelope) -> None:
        """Validate an envelope against its registered schema version."""
        if self.is_empty:
            return
        if envelope.selection_schema_version not in self._validators:
            raise UnsupportedSelectionSchemaVersion(
                envelope.selection_schema_version,
                available=list(self._validators.keys()),
            )
        validator = self._validators[envelope.selection_schema_version]
        if validator is not None:
            validator(dict(envelope.selections))

    def has(self, version: str) -> bool:
        return version in self._validators

    @property
    def available_versions(self) -> List[str]:
        return list(self._validators.keys())

    @property
    def is_empty(self) -> bool:
        return len(self._validators) == 0

    def clear(self) -> None:
        """Remove all registered schemas. Intended for testing only."""
        self._validators.clear()


# Module-level singletons
_journey_registry = JourneyStrategyRegistry()
_selection_registry = SelectionSchemaRegistry()


def get_journey_registry() -> JourneyStrategyRegistry:
    """Return the singleton journey strategy registry."""
    return _journey_registry


def get_selection_schema_registry() -> SelectionSchemaRegistry:
    """Return the singleton user-selection schema registry."""
    return _selection_registry


__all__ = [
    "COMPETENCY_COUNT",
    "JourneyError",
    "JourneyMethodologyNotConfigured",
    "UnsupportedJourneyVersion",
    "UnsupportedSelectionSchemaVersion",
    "JourneyInputError",
    "JourneyValidationError",
    "JourneyStatus",
    "JourneySelectionEnvelope",
    "JourneyCompetencyInput",
    "JourneyRecommendationInput",
    "JourneyItem",
    "JourneyRecommendationResult",
    "JourneyRecommendationStrategy",
    "JourneyStrategyRegistry",
    "SelectionSchemaRegistry",
    "SelectionValidator",
    "get_journey_registry",
    "get_selection_schema_registry",
]
