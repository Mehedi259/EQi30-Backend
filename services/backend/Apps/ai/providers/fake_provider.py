"""
In-memory fake LLM provider for tests.

This is a genuine implementation of
:class:`~app.providers.base.BaseLLMProvider`, not a mock object: it
participates in the same interface every real provider does, so services and
routes can depend on it in tests exactly as they depend on
:class:`~app.providers.openai_provider.OpenAIProvider` in production — no
network access, no real API key, fully deterministic.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Union

from Apps.ai.providers.base import (
    BaseLLMProvider,
    LLMCallOptions,
    LLMConfigurationError,
    LLMMessage,
    LLMResult,
    LLMUsage,
)

#: A scripted outcome: an ``Exception`` instance is raised as-is; anything
#: else is treated as the literal text of a successful reply.
ScriptedResponse = Union[str, BaseException]
ResponseFactory = Callable[[List[LLMMessage], LLMCallOptions], ScriptedResponse]


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic provider double for use in tests.

    Usage::

        provider = FakeLLMProvider(responses=["hello"])
        provider = FakeLLMProvider(responses=[LLMTimeoutError(...)])
        provider = FakeLLMProvider(response_factory=lambda messages, options: "...")

    Every call is recorded in ``self.calls`` so tests can assert on what was
    sent, without any of that inspection leaking provider-specific concerns
    into the caller under test.
    """

    def __init__(
        self,
        *,
        responses: Optional[List[ScriptedResponse]] = None,
        response_factory: Optional[ResponseFactory] = None,
        configured: bool = True,
        model: str = "fake-model",
    ) -> None:
        self._responses = list(responses) if responses is not None else None
        self._response_factory = response_factory
        self._configured = configured
        self._model = model
        self.calls: List[List[LLMMessage]] = []

    @property
    def name(self) -> str:
        return "fake"

    @property
    def default_model(self) -> str:
        return self._model

    @property
    def call_count(self) -> int:
        return len(self.calls)

    async def complete(
        self,
        messages: List[LLMMessage],
        options: Optional[LLMCallOptions] = None,
    ) -> LLMResult:
        options = options or LLMCallOptions()
        self.calls.append(list(messages))

        if not self._configured:
            raise LLMConfigurationError(
                f"{self.name} is not configured.", provider=self.name
            )

        outcome = self._next_outcome(messages, options)
        if isinstance(outcome, BaseException):
            raise outcome

        return LLMResult(
            provider=self.name,
            model=options.model or self._model,
            text=outcome,
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            latency_ms=0.0,
            request_id=options.request_id,
        )

    def _next_outcome(
        self, messages: List[LLMMessage], options: LLMCallOptions
    ) -> ScriptedResponse:
        if self._response_factory is not None:
            return self._response_factory(messages, options)
        if self._responses:
            if len(self._responses) == 1:
                return self._responses[0]
            return self._responses.pop(0)
        return "fake response"


__all__ = ["FakeLLMProvider", "ScriptedResponse", "ResponseFactory"]
