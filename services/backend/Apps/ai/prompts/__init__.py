"""
Versioned prompt architecture for the EQi-30 AI service.

This module is the shared engine every capability module in this package
(``system.py``, ``assessment.py``, ``recommendation.py``, ``journey.py``,
``chat.py``, ``safety.py``) builds on: a versioned ``PromptBuilder`` base
class, a per-prompt ``PromptRegistry``, typed value objects, and a typed
error hierarchy.

Design rules (from CLAUDE.md and this phase's instructions):

* **Prompt builders, not embedded strings.** Every prompt is a class with
  declared metadata (version, purpose, required inputs, output
  requirements, safety constraints), never a raw string built inline in a
  service or route.
* **Explicit inputs only.** A builder's ``render(**variables)`` accepts
  *only* the variables it has declared. Missing required variables and
  unexpected/undeclared variables are both hard errors — this is what "no
  hidden application state" means in code: nothing a builder produces can
  depend on anything the caller did not explicitly pass in.
* **Deterministic.** ``_build()`` is a pure function of the ``variables``
  dict — no clock, no randomness, no environment/config reads, no provider
  calls. The same inputs always render the same text.
* **No secrets.** Nothing in this package reads an API key or any other
  credential; prompts are pure text templates.
* **System/developer instructions are internal.** A ``RenderedPrompt``'s
  ``system`` text is server-side only. It must never be placed on any
  wire-level response schema (see ``app/schemas/``, whose cross-cutting
  tests already assert no schema exposes a system-prompt-shaped field).
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rest_framework import status
from pydantic import BaseModel, ConfigDict, Field

from Apps.ai.core.exceptions import AppException

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class PromptVariable(BaseModel):
    """Documents a single named input a prompt builder consumes.

    This is metadata, not a rendering mechanism — it exists so a builder's
    contract (what it needs, and why) is inspectable and testable rather
    than implicit in template code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=500)
    required: bool = True
    default: Optional[str] = Field(
        default=None,
        description=(
            "Value substituted by a builder when an optional variable is "
            "not supplied. Ignored for required variables."
        ),
    )


class RenderedPrompt(BaseModel):
    """The deterministic output of building a prompt.

    ``system`` carries the system/developer instruction text. It is
    internal to this service and must never be returned on any wire-level
    response. ``user`` carries the corresponding user-turn text built from
    the supplied variables.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    system: str
    user: str


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PromptError(AppException):
    """Base class for all prompt-architecture failures.

    These represent defects in how a service constructs a prompt (missing
    or undeclared variables, an unregistered version) — not end-user input
    errors, since no route calls into this package directly yet.
    """


class MissingPromptVariableError(PromptError):
    """A required variable was not supplied to ``render()``."""

    def __init__(self, prompt_id: str, version: str, missing: Sequence[str]):
        super().__init__(
            message=(
                f"Prompt '{prompt_id}' v{version} is missing required "
                f"variables: {list(missing)}."
            ),
            code="PROMPT_MISSING_VARIABLES",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "prompt_id": prompt_id,
                "version": version,
                "missing": list(missing),
            },
        )


class UnexpectedPromptVariableError(PromptError):
    """An undeclared variable was supplied to ``render()``.

    Rejecting these is what enforces "no hidden application state": every
    input a prompt can possibly use must be declared up front.
    """

    def __init__(self, prompt_id: str, version: str, unexpected: Sequence[str]):
        super().__init__(
            message=(
                f"Prompt '{prompt_id}' v{version} received undeclared "
                f"variables: {list(unexpected)}. Every input must be "
                f"explicitly declared as a PromptVariable."
            ),
            code="PROMPT_UNEXPECTED_VARIABLES",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "prompt_id": prompt_id,
                "version": version,
                "unexpected": list(unexpected),
            },
        )


class UnsupportedPromptVersionError(PromptError):
    """The requested prompt version is not registered."""

    def __init__(self, prompt_id: str, version: str, available: Sequence[str]):
        super().__init__(
            message=(
                f"Prompt '{prompt_id}' version '{version}' is not "
                f"registered. Available versions: "
                f"{list(available) if available else 'none'}."
            ),
            code="UNSUPPORTED_PROMPT_VERSION",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={
                "prompt_id": prompt_id,
                "requested_version": version,
                "available_versions": list(available),
            },
        )


class PromptNotConfiguredError(PromptError):
    """No builder at all is registered for this prompt_id."""

    def __init__(self, prompt_id: str):
        super().__init__(
            message=f"No prompt builder is registered for '{prompt_id}'.",
            code="PROMPT_NOT_CONFIGURED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"prompt_id": prompt_id},
        )


# ---------------------------------------------------------------------------
# Builder base class
# ---------------------------------------------------------------------------


class PromptBuilder(abc.ABC):
    """A single versioned prompt-construction strategy.

    Concrete builders declare their contract (``required_variables``,
    ``output_requirements``, ``safety_constraints``) and implement
    ``_build()`` as a pure function of the variables they declared.
    ``render()`` is the public, concrete entry point: it validates the
    supplied variables against the declared contract before delegating to
    ``_build()``, so every builder gets the same validation discipline for
    free.
    """

    @property
    @abc.abstractmethod
    def prompt_id(self) -> str:
        """Stable identifier for this prompt, e.g. ``'chat.turn'``."""
        ...

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Version identifier for this specific builder, e.g. ``'1.0'``."""
        ...

    @property
    @abc.abstractmethod
    def purpose(self) -> str:
        """Human-readable one-line description of what this prompt is for."""
        ...

    @property
    @abc.abstractmethod
    def required_variables(self) -> Tuple[PromptVariable, ...]:
        """The full set of variables this builder accepts (required + optional)."""
        ...

    @property
    @abc.abstractmethod
    def output_requirements(self) -> str:
        """Description of the shape/constraints expected of the LLM output."""
        ...

    @property
    @abc.abstractmethod
    def safety_constraints(self) -> Tuple[str, ...]:
        """The safety rules this prompt encodes."""
        ...

    def render(self, **variables: Any) -> RenderedPrompt:
        """Validate the supplied variables, then build the prompt.

        Raises:
            MissingPromptVariableError: a required variable was not supplied.
            UnexpectedPromptVariableError: an undeclared variable was supplied.
        """
        self._validate_variables(variables)
        system_text, user_text = self._build(dict(variables))
        return RenderedPrompt(
            prompt_id=self.prompt_id,
            version=self.version,
            system=system_text,
            user=user_text,
        )

    @abc.abstractmethod
    def _build(self, variables: Dict[str, Any]) -> Tuple[str, str]:
        """Return ``(system_text, user_text)``.

        Must be a pure function of ``variables`` — no I/O, no clock, no
        randomness, no reads from application config or global state.
        """
        ...

    def _validate_variables(self, variables: Dict[str, Any]) -> None:
        declared = {v.name for v in self.required_variables}
        required = {v.name for v in self.required_variables if v.required}
        provided = set(variables.keys())

        missing = sorted(required - provided)
        if missing:
            raise MissingPromptVariableError(self.prompt_id, self.version, missing)

        unexpected = sorted(provided - declared)
        if unexpected:
            raise UnexpectedPromptVariableError(
                self.prompt_id, self.version, unexpected
            )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PromptRegistry:
    """Versioned registry of builders for a single logical prompt.

    A registry is scoped to one ``prompt_id`` (e.g. ``'chat.turn'``). Each
    capability module owns one registry per distinct prompt it defines, and
    registers one or more versioned builders into it.
    """

    def __init__(self, prompt_id: str) -> None:
        self._prompt_id = prompt_id
        self._builders: Dict[str, PromptBuilder] = {}
        self._default_version: Optional[str] = None

    @property
    def prompt_id(self) -> str:
        return self._prompt_id

    def register(self, builder: PromptBuilder, *, set_default: bool = False) -> None:
        """Register a versioned builder. The first registration becomes default."""
        if builder.prompt_id != self._prompt_id:
            raise ValueError(
                f"Builder prompt_id {builder.prompt_id!r} does not match "
                f"registry prompt_id {self._prompt_id!r}."
            )
        self._builders[builder.version] = builder
        if set_default or self._default_version is None:
            self._default_version = builder.version

    def get(self, version: Optional[str] = None) -> PromptBuilder:
        """Resolve a builder by version, or the registered default.

        Raises:
            PromptNotConfiguredError: no builder registered at all.
            UnsupportedPromptVersionError: the requested version is unknown.
        """
        resolved = version if version is not None else self._default_version
        if resolved is None:
            raise PromptNotConfiguredError(self._prompt_id)
        try:
            return self._builders[resolved]
        except KeyError:
            raise UnsupportedPromptVersionError(
                self._prompt_id, resolved, available=list(self._builders.keys())
            ) from None

    def render(self, *, version: Optional[str] = None, **variables: Any) -> RenderedPrompt:
        """Resolve a builder by version (or default) and render it."""
        return self.get(version).render(**variables)

    @property
    def default_version(self) -> Optional[str]:
        return self._default_version

    @property
    def available_versions(self) -> List[str]:
        return list(self._builders.keys())

    @property
    def is_empty(self) -> bool:
        return len(self._builders) == 0

    def clear(self) -> None:
        """Remove all registered builders. Intended for testing only."""
        self._builders.clear()
        self._default_version = None


# ---------------------------------------------------------------------------
# Capability modules (imported last: they depend on the classes above)
# ---------------------------------------------------------------------------

from Apps.ai.prompts.system import SYSTEM_CORE_REGISTRY, SystemCorePromptV1, SystemCorePromptV2
from Apps.ai.prompts.safety import (
    SAFETY_GUARDRAILS_REGISTRY,
    SafetyGuardrailsPromptV1,
    SafetyGuardrailsPromptV2,
)
from Apps.ai.prompts.coaching import COACHING_BEHAVIOR_REGISTRY, CoachingBehaviorPromptV1
from Apps.ai.prompts.assessment import (
    ASSESSMENT_SUMMARY_REGISTRY,
    AssessmentSummaryPromptV1,
)
from Apps.ai.prompts.recommendation import (
    RECOMMENDATION_RATIONALE_REGISTRY,
    CompetencyRationalePromptV1,
)
from Apps.ai.prompts.journey import JOURNEY_NARRATIVE_REGISTRY, JourneyItemNarrativePromptV1
from Apps.ai.prompts.chat import (
    CHAT_TURN_REGISTRY,
    ChatTurnPromptV1,
    ChatTurnPromptV1_1,
    ChatTurnPromptV2,
)

__all__ = [
    # abstraction
    "PromptVariable",
    "RenderedPrompt",
    "PromptBuilder",
    "PromptRegistry",
    # errors
    "PromptError",
    "MissingPromptVariableError",
    "UnexpectedPromptVariableError",
    "UnsupportedPromptVersionError",
    "PromptNotConfiguredError",
    # system
    "SystemCorePromptV1",
    "SystemCorePromptV2",
    "SYSTEM_CORE_REGISTRY",
    # safety
    "SafetyGuardrailsPromptV1",
    "SafetyGuardrailsPromptV2",
    "SAFETY_GUARDRAILS_REGISTRY",
    # coaching
    "CoachingBehaviorPromptV1",
    "COACHING_BEHAVIOR_REGISTRY",
    # assessment
    "AssessmentSummaryPromptV1",
    "ASSESSMENT_SUMMARY_REGISTRY",
    # recommendation
    "CompetencyRationalePromptV1",
    "RECOMMENDATION_RATIONALE_REGISTRY",
    # journey
    "JourneyItemNarrativePromptV1",
    "JOURNEY_NARRATIVE_REGISTRY",
    # chat
    "ChatTurnPromptV1",
    "ChatTurnPromptV1_1",
    "ChatTurnPromptV2",
    "CHAT_TURN_REGISTRY",
]
