"""
Shared schema primitives for the EQi-30 AI service.

Design rules enforced here (see CLAUDE.md):

* The AI service is stateless. Schemas describe a single request/response
  exchange; they never model persisted user state.
* External integration fields are explicitly versioned so the backend
  contract can evolve without breaking older callers.
* Where a business rule is not yet available (competency codes, response
  scales, journey/selection taxonomy) the schema stays deliberately open
  and carries a version discriminator instead of inventing the rule.
* Requests are strict (``extra="forbid"``) so unsupported or unauthorized
  fields fail loudly rather than being silently ignored.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from Apps.ai.domain.abilities import ABILITY_COUNT, AbilityCode
from Apps.ai.domain.competencies import COMPETENCY_COUNT, CompetencyCode

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

#: Version of the AI service's own request/response contract. Callers send it
#: so the service can evolve payload shapes without breaking older clients.
CONTRACT_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Domain cardinality and identifiers
# ---------------------------------------------------------------------------
#
# ``COMPETENCY_COUNT``, ``ABILITY_COUNT``, ``CompetencyCode`` and
# ``AbilityCode`` are re-exported from :mod:`app.domain` so the wire contract
# and the canonical taxonomy can never drift apart. The domain package is the
# single source of truth; this module only describes payload shape.

#: An opaque identifier issued by the backend (assessment item, ability,
#: journey reference, ...). Treated as a correlation key, never interpreted.
ExternalRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]

#: AI-assigned competency priority. Valid values are 1..COMPETENCY_COUNT.
AIPriority = Annotated[int, Field(ge=1, le=COMPETENCY_COUNT)]

#: BCP-47 style locale tag (e.g. "en", "en-GB"). Format only, no allow-list.
LocaleTag = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=35,
        pattern=r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$",
    ),
]


# ---------------------------------------------------------------------------
# Base models
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    """Base for all AI service payloads.

    ``extra="forbid"`` is what makes unsupported fields — including
    ``user_priority``, which this service must never accept or return — a
    hard validation error instead of a silently dropped key.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class VersionedRequest(StrictModel):
    """Base for every inbound request from the Django backend."""

    contract_version: str = Field(
        default=CONTRACT_VERSION,
        min_length=1,
        max_length=16,
        description="Version of the AI service request contract used by the caller.",
    )
    request_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Correlation ID supplied by Django; echoed back on the response.",
    )


class VersionedResponse(StrictModel):
    """Base for every outbound AI result returned to the Django backend."""

    contract_version: str = Field(
        default=CONTRACT_VERSION,
        min_length=1,
        max_length=16,
        description="Version of the AI service response contract.",
    )
    request_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Correlation ID echoed from the originating request.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp at which the AI result was produced.",
    )


# ---------------------------------------------------------------------------
# Reusable validators
# ---------------------------------------------------------------------------


def ensure_unique(values: Sequence[Any], *, label: str) -> None:
    """Raise ``ValueError`` if ``values`` contains duplicates."""
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        rendered = ", ".join(repr(d) for d in duplicates)
        raise ValueError(f"duplicate {label}: {rendered}")


def ensure_exact_count(values: Sequence[Any], *, expected: int, label: str) -> None:
    """Raise ``ValueError`` unless ``values`` holds exactly ``expected`` items."""
    if len(values) != expected:
        raise ValueError(f"expected exactly {expected} {label}, got {len(values)}")


def ensure_priority_permutation(
    priorities: Sequence[int], *, expected: int = COMPETENCY_COUNT
) -> None:
    """Raise unless ``priorities`` is exactly 1..``expected``, each used once.

    This enforces a total ordering with no gaps, no duplicates and no
    out-of-range ranks.
    """
    ensure_exact_count(priorities, expected=expected, label="priorities")
    ensure_unique(priorities, label="priority")
    if sorted(priorities) != list(range(1, expected + 1)):
        raise ValueError(
            f"priorities must be exactly 1..{expected} with no gaps; got {sorted(priorities)}"
        )


# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------


class ErrorCode(str, Enum):
    """Stable machine-readable error codes.

    Django integrates against these values, never against ``message`` text.
    """

    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    UNSUPPORTED_CONTRACT_VERSION = "UNSUPPORTED_CONTRACT_VERSION"
    SCORING_METHODOLOGY_NOT_SPECIFIED = "SCORING_METHODOLOGY_NOT_SPECIFIED"


# --- Phase 1 contract (unchanged; response handlers depend on this shape) ---


class BaseResponse(BaseModel):
    success: bool = True
    request_id: Optional[str] = None


class ErrorDetails(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Any] = Field(
        default=None, description="Additional context or validation details"
    )


class ErrorResponse(BaseResponse):
    """Standard AI error response returned for every failure path."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request payload or parameter validation failed",
                        "details": [
                            {
                                "field": "body -> message",
                                "message": "String should have at least 1 character",
                                "type": "string_too_short",
                            }
                        ],
                    },
                    "request_id": "django-req-1a2b3c4d",
                }
            ]
        }
    )

    success: bool = False
    error: ErrorDetails


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "healthy",
                    "service": "EQi-30 AI Service",
                    "version": "1.0.0",
                    "environment": "production",
                    "timestamp": "2026-01-15T10:30:00+00:00",
                }
            ]
        }
    )

    status: str = Field(default="healthy", description="Status of the service")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Runtime environment")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )


__all__ = [
    "CONTRACT_VERSION",
    "COMPETENCY_COUNT",
    "ABILITY_COUNT",
    "CompetencyCode",
    "AbilityCode",
    "ExternalRef",
    "AIPriority",
    "LocaleTag",
    "StrictModel",
    "VersionedRequest",
    "VersionedResponse",
    "ensure_unique",
    "ensure_exact_count",
    "ensure_priority_permutation",
    "ErrorCode",
    "BaseResponse",
    "ErrorDetails",
    "ErrorResponse",
    "HealthResponse",
]
