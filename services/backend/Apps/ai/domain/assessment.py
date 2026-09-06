"""
Assessment domain models for the EQi-30 AI service.

This module defines the **intermediate representation** that sits between
the wire-format schemas (``app.schemas.assessment``) and the downstream
scoring layer (``app.services.scoring_service``).

Design rules (from CLAUDE.md):

* **No psychometric logic** — this module models *structure*, not behaviour.
  It has no scoring formula, no weight, no normalization and no threshold.
* **Stateless** — an ``AssessmentResult`` is a value object produced from a
  single request.  Nothing is persisted; Django owns persistence.
* **Deterministic** — the same input always produces the same result.
* **Validated** — domain invariants are checked at construction time.
  An invalid assessment fails immediately instead of reaching the scoring
  layer.

Pipeline position::

    AssessmentRequest (wire)
         ↓
    AssessmentService.process()
         ↓  validates, transforms
    AssessmentResult (domain)
         ↓  passed to
    ScoringService.score()
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Apps.ai.core.exceptions import AppException
from rest_framework import status


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AssessmentError(AppException):
    """Base class for assessment-domain failures."""


class AssessmentVersionNotSupported(AssessmentError):
    """The instrument version is not recognised by the service."""

    def __init__(self, version: str, available: Sequence[str]):
        super().__init__(
            message=(
                f"Instrument version '{version}' is not supported. "
                f"Supported versions: {list(available) if available else 'none'}."
            ),
            code="UNSUPPORTED_INSTRUMENT_VERSION",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={
                "requested_version": version,
                "supported_versions": list(available),
            },
        )


class AssessmentValidationError(AssessmentError):
    """Assessment input fails domain-level validation."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="ASSESSMENT_VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class DuplicateAnswerError(AssessmentValidationError):
    """Two or more answers reference the same item."""

    def __init__(self, item_ids: List[str]):
        super().__init__(
            message=f"Duplicate answer item_ids: {item_ids}",
            details={"duplicate_item_ids": item_ids},
        )


class InvalidAnswerError(AssessmentValidationError):
    """An individual answer is structurally invalid."""

    def __init__(self, item_id: str, reason: str):
        super().__init__(
            message=f"Invalid answer for item '{item_id}': {reason}",
            details={"item_id": item_id, "reason": reason},
        )


class UnknownItemReferenceError(AssessmentValidationError):
    """An item_id does not exist in the instrument specification."""

    def __init__(self, item_id: str, instrument_version: str):
        super().__init__(
            message=(
                f"Unknown item reference '{item_id}' for instrument "
                f"version '{instrument_version}'."
            ),
            details={
                "item_id": item_id,
                "instrument_version": instrument_version,
            },
        )


# ---------------------------------------------------------------------------
# Assessment status
# ---------------------------------------------------------------------------


class AssessmentStatus(str, Enum):
    """Processing status of an assessment result."""

    VALIDATED = "validated"
    SCORED = "scored"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------


class AssessmentAnswer(BaseModel):
    """A single validated answer from the assessment.

    This is the domain representation of a user's response to one
    assessment item.  It mirrors ``AssessmentItemResponse`` but belongs
    to the domain layer rather than the wire contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Assessment item identifier from the instrument.",
    )
    value: float = Field(
        ...,
        allow_inf_nan=False,
        description=(
            "Raw response value.  Valid range is defined by the instrument "
            "specification, not by this model."
        ),
    )
    ability_code: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Ability code this item maps to, if the instrument specification "
            "provides item-to-ability mapping.  None when the mapping is not "
            "available."
        ),
    )


class AssessmentInput(BaseModel):
    """Validated collection of assessment answers with metadata.

    Constructed by ``AssessmentService.process()`` after domain-level
    validation has passed.  This is the canonical input to the scoring
    pipeline.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_ref: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Opaque user reference from the backend (correlation only).",
    )
    instrument_version: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Version of the assessment instrument.",
    )
    scoring_version: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Requested scoring methodology version (None = use default).",
    )
    answers: List[AssessmentAnswer] = Field(
        ...,
        min_length=1,
        description="Validated assessment answers.",
    )
    request_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Correlation ID from the originating request.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for backend-supplied context.",
    )
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the assessment was received for processing.",
    )

    @property
    def answer_count(self) -> int:
        return len(self.answers)

    @property
    def item_ids(self) -> List[str]:
        return [a.item_id for a in self.answers]

    @model_validator(mode="after")
    def _validate_unique_item_ids(self) -> "AssessmentInput":
        seen: set[str] = set()
        duplicates: list[str] = []
        for a in self.answers:
            if a.item_id in seen and a.item_id not in duplicates:
                duplicates.append(a.item_id)
            seen.add(a.item_id)
        if duplicates:
            raise ValueError(f"Duplicate item_ids in answers: {duplicates}")
        return self


class AssessmentResult(BaseModel):
    """Intermediate assessment representation produced by AssessmentService.

    Carries the validated input and processing metadata.  This is what
    the scoring layer receives — it is *not* the final API response
    (that is ``AssessmentResponse`` from ``app.schemas.assessment``).
    """

    model_config = ConfigDict(extra="forbid")

    assessment_input: AssessmentInput = Field(
        ...,
        description="The validated assessment input.",
    )
    status: AssessmentStatus = Field(
        default=AssessmentStatus.VALIDATED,
        description="Current processing status.",
    )
    validation_warnings: List[str] = Field(
        default_factory=list,
        description=(
            "Non-fatal warnings discovered during validation (e.g. taxonomy "
            "validation skipped because canonical data is not yet populated)."
        ),
    )
    validated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of validation completion.",
    )

    @property
    def user_ref(self) -> str:
        return self.assessment_input.user_ref

    @property
    def instrument_version(self) -> str:
        return self.assessment_input.instrument_version

    @property
    def scoring_version(self) -> Optional[str]:
        return self.assessment_input.scoring_version

    @property
    def request_id(self) -> Optional[str]:
        return self.assessment_input.request_id

    @property
    def answer_count(self) -> int:
        return self.assessment_input.answer_count


# ---------------------------------------------------------------------------
# Instrument version registry
# ---------------------------------------------------------------------------


class InstrumentVersionConfig(BaseModel):
    """Configuration for a supported assessment instrument version.

    When the backend provides a full item catalogue, ``known_item_ids``
    enables item-reference validation.  Until then, the field remains
    ``None`` and item validation is skipped (with a warning).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(..., min_length=1, max_length=32)
    description: str = Field(default="")
    expected_item_count: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Expected number of items in this instrument version.  "
            "None when not yet specified by the backend."
        ),
    )
    known_item_ids: Optional[frozenset[str]] = Field(
        default=None,
        description=(
            "Complete set of item_ids for this version. None when the "
            "item catalogue has not been supplied by the backend."
        ),
    )
    value_min: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Minimum allowed response value (inclusive).",
    )
    value_max: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Maximum allowed response value (inclusive).",
    )


class InstrumentRegistry:
    """Registry of supported assessment instrument versions.

    Similar in spirit to ``ScoringStrategyRegistry``: each instrument
    version is registered explicitly and looked up at request time.
    """

    def __init__(self) -> None:
        self._versions: Dict[str, InstrumentVersionConfig] = {}
        self._default_version: Optional[str] = None

    def register(
        self,
        config: InstrumentVersionConfig,
        *,
        set_default: bool = False,
    ) -> None:
        self._versions[config.version] = config
        if set_default or self._default_version is None:
            self._default_version = config.version

    def get(self, version: str) -> InstrumentVersionConfig:
        try:
            return self._versions[version]
        except KeyError:
            raise AssessmentVersionNotSupported(
                version, available=list(self._versions.keys())
            )

    def has(self, version: str) -> bool:
        return version in self._versions

    @property
    def default_version(self) -> Optional[str]:
        return self._default_version

    @property
    def supported_versions(self) -> List[str]:
        return list(self._versions.keys())

    @property
    def is_empty(self) -> bool:
        return len(self._versions) == 0

    def clear(self) -> None:
        self._versions.clear()
        self._default_version = None


# Module-level singleton
_instrument_registry = InstrumentRegistry()


def get_instrument_registry() -> InstrumentRegistry:
    """Return the singleton instrument version registry."""
    return _instrument_registry


__all__ = [
    "AssessmentError",
    "AssessmentVersionNotSupported",
    "AssessmentValidationError",
    "DuplicateAnswerError",
    "InvalidAnswerError",
    "UnknownItemReferenceError",
    "AssessmentStatus",
    "AssessmentAnswer",
    "AssessmentInput",
    "AssessmentResult",
    "InstrumentVersionConfig",
    "InstrumentRegistry",
    "get_instrument_registry",
]
