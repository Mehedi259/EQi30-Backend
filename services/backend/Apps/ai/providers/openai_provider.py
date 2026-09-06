"""
OpenAI implementation of :class:`~app.providers.base.BaseLLMProvider`.

All OpenAI-specific concerns live in this module and nowhere else: HTTP
payload shape, authentication scheme, response parsing, and status-code
error mapping. Callers never see an ``httpx`` exception or an OpenAI error
payload — every failure is normalized into a typed
:class:`~app.providers.base.LLMProviderError` subclass before it leaves
``complete()``.

The OpenAI REST API is called directly over ``httpx`` rather than through the
``openai`` SDK, so retry, timeout and error-normalization behavior stay fully
owned by this module instead of a third-party client's defaults.

Configuration is read exclusively from environment variables
(``OPENAI_*``), isolated in :class:`OpenAIProviderSettings` so no OpenAI
concept leaks into the shared application ``Settings``. The API key is never
hardcoded, never logged, and never included in a raised error's message or
details.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from Apps.ai.core.logging import get_logger
from Apps.ai.providers.base import (
    BaseLLMProvider,
    LLMAuthenticationError,
    LLMCallOptions,
    LLMConfigurationError,
    LLMMessage,
    LLMProviderError,
    LLMProviderUnavailableError,
    LLMRateLimitError,
    LLMResponseValidationError,
    LLMResult,
    LLMTimeoutError,
    LLMUsage,
    retry_with_backoff,
)

logger = get_logger(__name__)

_CHAT_COMPLETIONS_PATH = "/chat/completions"

#: HTTP status codes worth retrying: rate limiting and transient server errors.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class OpenAIProviderSettings(BaseSettings):
    """OpenAI-specific configuration, isolated from the global app ``Settings``.

    Kept provider-local so no OpenAI-specific concept leaks outside
    ``app/providers/``. All values are read from environment variables;
    nothing is hardcoded.
    """

    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: Optional[str] = Field(
        default=None,
        description=(
            "OpenAI API key. Read from OPENAI_API_KEY. Never hardcoded, "
            "never logged, never included in any error."
        ),
    )
    model: str = Field(default="gpt-4o-mini", min_length=1)
    base_url: str = Field(default="https://api.openai.com/v1", min_length=1)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=800, gt=0)
    timeout_seconds: float = Field(default=20.0, gt=0)
    max_retries: int = Field(default=2, ge=0)


class _RetryableHTTPStatus(Exception):
    """Internal signal carrying a response whose status code is retryable.

    Never raised past ``complete()`` — always normalized into a typed
    ``LLMProviderError`` first.
    """

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        super().__init__(f"retryable status {response.status_code}")


class OpenAIProvider(BaseLLMProvider):
    """Calls the OpenAI Chat Completions API over HTTP."""

    def __init__(
        self,
        settings: Optional[OpenAIProviderSettings] = None,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        sleep: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> None:
        self._settings = settings or OpenAIProviderSettings()
        self._injected_client = http_client
        self._owned_client: Optional[httpx.AsyncClient] = None
        self._sleep = sleep or _default_sleep

    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return self._settings.model

    @property
    def _http_client(self) -> httpx.AsyncClient:
        if self._injected_client is not None:
            return self._injected_client
        if self._owned_client is None:
            self._owned_client = httpx.AsyncClient()
        return self._owned_client

    async def aclose(self) -> None:
        """Release the HTTP client this provider created, if any.

        No-op when a client was injected (the caller owns its lifecycle).
        """
        if self._owned_client is not None:
            await self._owned_client.aclose()
            self._owned_client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: List[LLMMessage],
        options: Optional[LLMCallOptions] = None,
    ) -> LLMResult:
        options = options or LLMCallOptions()

        if not self._settings.api_key:
            raise LLMConfigurationError(
                f"{self.name} API key is not configured. Set OPENAI_API_KEY.",
                provider=self.name,
            )

        model = options.model or self._settings.model
        temperature = (
            self._settings.temperature
            if options.temperature is None
            else options.temperature
        )
        max_tokens = options.max_tokens or self._settings.max_tokens
        timeout_seconds = options.timeout_seconds or self._settings.timeout_seconds
        max_retries = (
            self._settings.max_retries
            if options.max_retries is None
            else options.max_retries
        )

        payload: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [m.model_dump() for m in messages],
        }
        if options.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        # Never logged, never placed in any raised error's message/details.
        headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }
        if options.request_id:
            headers["X-Request-ID"] = options.request_id

        async def attempt() -> httpx.Response:
            response = await self._http_client.post(
                f"{self._settings.base_url}{_CHAT_COMPLETIONS_PATH}",
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )
            if response.status_code in _RETRYABLE_STATUS_CODES:
                raise _RetryableHTTPStatus(response)
            return response

        start = time.perf_counter()
        try:
            response = await retry_with_backoff(
                attempt,
                max_retries=max_retries,
                is_retryable=self._is_retryable,
                sleep=self._sleep,
            )
        except _RetryableHTTPStatus as exc:
            error = self._normalize_status_error(exc.response)
            self._log_failure(error, options=options, start=start)
            raise error from None
        except httpx.TimeoutException as exc:
            error = LLMTimeoutError(
                f"{self.name} request timed out after {timeout_seconds}s.",
                provider=self.name,
                timeout_seconds=timeout_seconds,
            )
            self._log_failure(error, options=options, start=start)
            raise error from exc
        except httpx.TransportError as exc:
            error = LLMProviderUnavailableError(
                f"Could not reach {self.name}.", provider=self.name
            )
            self._log_failure(error, options=options, start=start)
            raise error from exc

        if response.status_code >= 400:
            error = self._normalize_status_error(response)
            self._log_failure(error, options=options, start=start)
            raise error

        latency_ms = (time.perf_counter() - start) * 1000
        result = self._parse_success_response(
            response, model=model, request_id=options.request_id, latency_ms=latency_ms
        )
        logger.info(
            f"{self.name} call succeeded: model={result.model!r} "
            f"status={response.status_code} latency_ms={latency_ms:.1f} "
            f"request_id={options.request_id!r}"
        )
        return result

    # ------------------------------------------------------------------
    # Internal: retry classification
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        return isinstance(
            exc, (_RetryableHTTPStatus, httpx.TimeoutException, httpx.TransportError)
        )

    # ------------------------------------------------------------------
    # Internal: response parsing
    # ------------------------------------------------------------------

    def _parse_success_response(
        self,
        response: httpx.Response,
        *,
        model: str,
        request_id: Optional[str],
        latency_ms: float,
    ) -> LLMResult:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMResponseValidationError(
                f"{self.name} response body was not valid JSON.",
                provider=self.name,
                details=str(exc),
            ) from exc

        if not isinstance(payload, dict):
            raise LLMResponseValidationError(
                f"{self.name} response body was not a JSON object.",
                provider=self.name,
                details=f"got {type(payload).__name__}",
            )

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMResponseValidationError(
                f"{self.name} response did not contain any choices.",
                provider=self.name,
                details={"keys": list(payload.keys())},
            )

        first_choice = choices[0]
        message = first_choice.get("message") if isinstance(first_choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise LLMResponseValidationError(
                f"{self.name} response choice did not contain message content.",
                provider=self.name,
            )

        usage_payload = payload.get("usage")
        usage_payload = usage_payload if isinstance(usage_payload, dict) else {}
        usage = LLMUsage(
            prompt_tokens=usage_payload.get("prompt_tokens"),
            completion_tokens=usage_payload.get("completion_tokens"),
            total_tokens=usage_payload.get("total_tokens"),
        )

        return LLMResult(
            provider=self.name,
            model=payload.get("model") or model,
            text=content,
            finish_reason=first_choice.get("finish_reason"),
            usage=usage,
            latency_ms=latency_ms,
            request_id=request_id,
        )

    # ------------------------------------------------------------------
    # Internal: error normalization
    # ------------------------------------------------------------------

    def _normalize_status_error(self, response: httpx.Response) -> LLMProviderError:
        status_code = response.status_code
        message = self._extract_error_message(response)

        if status_code in (401, 403):
            return LLMAuthenticationError(
                f"{self.name} rejected the configured credentials: {message}",
                provider=self.name,
            )
        if status_code == 429:
            return LLMRateLimitError(
                f"{self.name} rate-limited this request: {message}",
                provider=self.name,
            )
        if status_code in _RETRYABLE_STATUS_CODES:
            return LLMProviderUnavailableError(
                f"{self.name} returned a server error ({status_code}): {message}",
                provider=self.name,
            )
        return LLMProviderUnavailableError(
            f"{self.name} returned an unexpected error status {status_code}: {message}",
            provider=self.name,
        )

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = response.text
            return text[:200] if text else f"HTTP {response.status_code}"
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return error["message"]
        return f"HTTP {response.status_code}"

    def _log_failure(
        self, error: LLMProviderError, *, options: LLMCallOptions, start: float
    ) -> None:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            f"{self.name} call failed: code={error.code} "
            f"latency_ms={latency_ms:.1f} request_id={options.request_id!r}"
        )


async def _default_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


__all__ = ["OpenAIProvider", "OpenAIProviderSettings"]
