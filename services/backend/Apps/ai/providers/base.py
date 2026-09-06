"""
LLM provider abstraction for the EQi-30 AI service.

This module defines the **provider-agnostic** interface every LLM backend
must implement, plus the normalized error hierarchy, value objects and a
generic retry helper shared by all providers.

Design rules (from CLAUDE.md):

* **All LLM calls go through this abstraction.** No provider-specific code
  (HTTP payload shape, auth scheme, response parsing) may appear outside
  ``app/providers/``. Services depend on ``BaseLLMProvider``, never on a
  concrete provider or a third-party SDK directly.
* **API keys come from environment variables only**, are never hardcoded,
  never logged, and never appear in a raised error's message or details.
* **Every provider failure is normalized** into one of the typed
  ``LLMProviderError`` subclasses defined here, so callers (and the global
  exception handlers) never see a raw SDK/HTTP exception.
* This module implements **no chatbot logic and no prompt templates** — it
  is transport plus normalization only.
"""

from __future__ import annotations

import abc
import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, TypeVar

from rest_framework import status
from pydantic import BaseModel, ConfigDict, Field

from Apps.ai.core.exceptions import AppException

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Normalized error hierarchy
# ---------------------------------------------------------------------------


class LLMProviderError(AppException):
    """Base class for every normalized LLM provider failure.

    Every concrete provider MUST catch its own SDK/HTTP exceptions and raise
    one of the subclasses below instead of letting a provider-specific
    exception type escape ``complete()``.
    """


class LLMConfigurationError(LLMProviderError):
    """The provider is missing required configuration (e.g. no API key).

    Raised before any network call is attempted.
    """

    def __init__(self, message: str, *, provider: str):
        super().__init__(
            message=message,
            code="LLM_PROVIDER_NOT_CONFIGURED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": provider},
        )


class LLMTimeoutError(LLMProviderError):
    """The provider did not respond within the configured timeout."""

    def __init__(self, message: str, *, provider: str, timeout_seconds: float):
        super().__init__(
            message=message,
            code="LLM_PROVIDER_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details={"provider": provider, "timeout_seconds": timeout_seconds},
        )


class LLMRateLimitError(LLMProviderError):
    """The provider rejected the call due to rate limiting (retries exhausted)."""

    def __init__(self, message: str, *, provider: str):
        super().__init__(
            message=message,
            code="LLM_PROVIDER_RATE_LIMITED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": provider},
        )


class LLMAuthenticationError(LLMProviderError):
    """The provider rejected the configured credentials.

    This means the request reached the provider and was rejected — never
    that our own key value was invalid in shape. The key itself never
    appears in this error.
    """

    def __init__(self, message: str, *, provider: str):
        super().__init__(
            message=message,
            code="LLM_PROVIDER_AUTHENTICATION_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"provider": provider},
        )


class LLMProviderUnavailableError(LLMProviderError):
    """The provider could not be reached, or returned a server-side error
    (retries exhausted where the failure was retryable)."""

    def __init__(self, message: str, *, provider: str):
        super().__init__(
            message=message,
            code="LLM_PROVIDER_UNAVAILABLE",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"provider": provider},
        )


class LLMResponseValidationError(LLMProviderError):
    """The provider responded, but the response could not be trusted/parsed.

    Raised for malformed JSON, missing expected fields, or a structured
    output request whose payload does not parse as an object. This is the
    boundary that enforces "never trust raw LLM output".
    """

    def __init__(self, message: str, *, provider: str, details: Optional[Any] = None):
        merged_details: Dict[str, Any] = {"provider": provider}
        if details is not None:
            merged_details["reason"] = details
        super().__init__(
            message=message,
            code="LLM_PROVIDER_INVALID_RESPONSE",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=merged_details,
        )


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

Role = Literal["system", "user", "assistant"]


class LLMMessage(BaseModel):
    """A single provider-facing conversation turn.

    This is the internal transport representation passed from a service to
    a provider. It intentionally allows ``system`` (unlike the wire-level
    ``ChatMessage`` schema, which forbids it from external callers) because
    constructing the system instruction is this service's own responsibility
    and never the caller's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Role
    content: str = Field(..., min_length=1)


class LLMUsage(BaseModel):
    """Token usage metadata, reported when the provider makes it available."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_tokens: Optional[int] = Field(default=None, ge=0)
    completion_tokens: Optional[int] = Field(default=None, ge=0)
    total_tokens: Optional[int] = Field(default=None, ge=0)


class LLMCallOptions(BaseModel):
    """Per-call configuration overrides.

    Every field is optional; a provider falls back to its own configured
    default when a field is unset. Nothing here is provider-specific.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: Optional[str] = Field(default=None, min_length=1)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    timeout_seconds: Optional[float] = Field(default=None, gt=0)
    max_retries: Optional[int] = Field(default=None, ge=0)
    response_format: Literal["text", "json"] = "text"
    request_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Correlation ID propagated for tracing. Never a secret.",
    )


class LLMResult(BaseModel):
    """Normalized result of a single LLM call, common to every provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str
    text: str
    structured: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    latency_ms: float = Field(..., ge=0.0)
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------


class BaseLLMProvider(abc.ABC):
    """Abstract base every LLM provider implementation must satisfy.

    Concrete providers own model selection, temperature, timeout and retry
    configuration, request/response translation, and error normalization.
    They must raise only ``LLMProviderError`` subclasses — no SDK-specific
    or raw HTTP exception may escape ``complete()``.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable provider identifier, e.g. ``'openai'``."""
        ...

    @property
    @abc.abstractmethod
    def default_model(self) -> str:
        """The model used when a call does not override one."""
        ...

    @abc.abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        options: Optional[LLMCallOptions] = None,
    ) -> LLMResult:
        """Send a conversation to the provider and return a normalized result.

        Must raise only ``LLMProviderError`` subclasses.
        """
        ...

    async def complete_json(
        self,
        messages: List[LLMMessage],
        options: Optional[LLMCallOptions] = None,
    ) -> LLMResult:
        """Call the provider and require the reply to parse as a JSON object.

        This is generic structured-output support: it parses and validates
        shape only. It defines no schema, no prompt and no business meaning
        for the parsed object — that is the caller's responsibility.
        """
        effective_options = (options or LLMCallOptions()).model_copy(
            update={"response_format": "json"}
        )
        result = await self.complete(messages, effective_options)
        structured = self._parse_json_object(result.text)
        return result.model_copy(update={"structured": structured})

    def _parse_json_object(self, text: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseValidationError(
                f"{self.name} response was not valid JSON.",
                provider=self.name,
                details=str(exc),
            ) from exc
        if not isinstance(parsed, dict):
            raise LLMResponseValidationError(
                f"{self.name} response JSON must be an object at the top level.",
                provider=self.name,
                details=f"got {type(parsed).__name__}",
            )
        return parsed


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------


async def retry_with_backoff(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    is_retryable: Callable[[BaseException], bool],
    base_delay_seconds: float = 0.5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run ``operation`` with exponential backoff on retryable failures.

    Provider-agnostic: any provider can reuse this rather than each
    reimplementing its own retry loop. ``sleep`` is injectable so tests can
    exercise real retry counts without real wall-clock delay.
    """
    attempt = 0
    while True:
        try:
            return await operation()
        except BaseException as exc:
            if attempt >= max_retries or not is_retryable(exc):
                raise
            await sleep(base_delay_seconds * (2**attempt))
            attempt += 1


__all__ = [
    "LLMProviderError",
    "LLMConfigurationError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "LLMProviderUnavailableError",
    "LLMResponseValidationError",
    "Role",
    "LLMMessage",
    "LLMUsage",
    "LLMCallOptions",
    "LLMResult",
    "BaseLLMProvider",
    "retry_with_backoff",
]
