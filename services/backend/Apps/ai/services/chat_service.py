"""
Chat orchestration service for the EQi-30 chatbot.

Pipeline (matches this phase's specified architecture)::

    ChatRequest (already validated by Pydantic/FastAPI)
         |
    SafetyService.check_input()      -> may short-circuit to a blocked ChatResponse
         |
    ContextService.render_context()  -> deterministic, bounded prompt inputs
    ContextService.render_history()  -> deterministic, bounded provider messages
         |
    app.prompts.chat.CHAT_TURN_REGISTRY.render()  -> RenderedPrompt (system + user text)
         |
    BaseLLMProvider.complete()       -> LLMResult (errors propagate; see below)
         |
    SafetyService.check_output()     -> may short-circuit to a blocked ChatResponse
         |
    ChatResponse

Statelessness
-------------
This service holds no conversation memory and performs no persistence and no
database access of any kind. Every input it needs — locale, competency,
ability, journey, progress, conversation history, and the current message —
arrives explicitly on the ``ChatRequest``. It never invents user information
or progress that was not supplied, and it never claims an action was
performed that this service did not actually perform (it performs none).

Provider error handling
------------------------
Provider failures are typed ``LLMProviderError`` subclasses (see
``app/providers/base.py``) and are deliberately **not** caught here. They
propagate to the globally registered exception handlers, which already map
each one to the correct HTTP status and a structured ``ErrorResponse``.
Catching and re-wrapping them here would only risk losing that already
correct, already tested mapping (see tests/unit/test_openai_provider.py).

Secrecy
-------
The rendered system/developer prompt text is used only to build the provider
call and, for output validation, to detect leakage. It is never placed on
``ChatResponse`` — only ``prompt_version`` (an opaque version string) is
returned, so a call remains reproducible without exposing the instructions
themselves.
"""

from __future__ import annotations

from typing import Optional

from Apps.ai.core.config import get_settings
from Apps.ai.core.logging import get_logger
from Apps.ai.prompts.chat import CHAT_TURN_REGISTRY
from Apps.ai.providers.base import BaseLLMProvider, LLMCallOptions, LLMMessage
from Apps.ai.providers.openai_provider import OpenAIProvider
from Apps.ai.schemas.chat import ChatRequest, ChatResponse
from Apps.ai.services.context_service import ContextService
from Apps.ai.services.safety_service import SafetyService

logger = get_logger(__name__)

#: Used only when Django omits ``locale``. A documented technical default,
#: not an invented business rule.
DEFAULT_LOCALE = "en"

#: Fixed, non-generated refusal used whenever a safety check blocks a turn.
#: Deliberately not LLM-generated: a blocked turn must never depend on the
#: very model output that triggered the block.
_SAFE_FALLBACK_REPLY = (
    "I can't help with that request. Let's keep our conversation focused on "
    "your EQi-30 journey."
)


class ChatService:
    """Orchestrates a single stateless chatbot turn."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        context_service: Optional[ContextService] = None,
        safety_service: Optional[SafetyService] = None,
        *,
        prompt_version: Optional[str] = None,
    ) -> None:
        self._provider = provider or OpenAIProvider()
        self._context = context_service or ContextService()
        self._safety = safety_service or SafetyService()
        self._prompt_version = prompt_version

    async def respond(
        self,
        request: ChatRequest,
        *,
        request_id: Optional[str] = None,
    ) -> ChatResponse:
        """Produce a single chat turn reply.

        Raises:
            LLMProviderError subclasses: propagated unchanged from the
                configured provider (timeout, unavailable, rate limited,
                misconfigured, invalid response). See module docstring.
        """
        correlation_id = request_id or request.request_id

        input_check = self._safety.check_input(
            request.message, request.history, request.context
        )
        if input_check.flagged:
            logger.warning(
                f"Chat turn blocked at input safety check: "
                f"user_ref={request.user_ref!r} reasons={list(input_check.reasons)}"
            )
            return self._blocked_response(request, correlation_id, stage="input")

        rendered_context = self._context.render_context(request.context)
        provider_history = self._context.render_history(request.history)

        product_name = get_settings().PROJECT_NAME
        locale = request.locale or DEFAULT_LOCALE

        rendered_prompt = CHAT_TURN_REGISTRY.render(
            version=self._prompt_version,
            product_name=product_name,
            locale=locale,
            journey_context=rendered_context.journey_context,
            competency_context=rendered_context.competency_context,
            ability_context=rendered_context.ability_context,
            progress_context=rendered_context.progress_context,
            user_message=request.message,
        )

        messages = (
            [LLMMessage(role="system", content=rendered_prompt.system)]
            + provider_history
            + [LLMMessage(role="user", content=rendered_prompt.user)]
        )

        result = await self._provider.complete(
            messages, LLMCallOptions(request_id=correlation_id)
        )

        grounding_context_supplied = any(
            (
                request.context.journey,
                request.context.competency,
                request.context.ability,
                request.context.progress,
            )
        )
        output_check = self._safety.check_output(
            result.text,
            system_prompt=rendered_prompt.system,
            grounding_context_supplied=grounding_context_supplied,
        )
        if output_check.flagged:
            logger.warning(
                f"Chat turn blocked at output safety check: "
                f"user_ref={request.user_ref!r} reasons={list(output_check.reasons)}"
            )
            return self._blocked_response(
                request,
                correlation_id,
                stage="output",
                prompt_version=rendered_prompt.version,
            )

        logger.info(
            f"Chat turn completed: user_ref={request.user_ref!r} "
            f"prompt_version={rendered_prompt.version!r} "
            f"provider={result.provider!r} finish_reason={result.finish_reason!r}"
        )

        return ChatResponse(
            user_ref=request.user_ref,
            reply=result.text,
            finish_reason=result.finish_reason,
            safety_blocked=False,
            prompt_version=rendered_prompt.version,
            request_id=correlation_id,
            metadata={"provider": result.provider, "model": result.model},
        )

    def _blocked_response(
        self,
        request: ChatRequest,
        correlation_id: Optional[str],
        *,
        stage: str,
        prompt_version: Optional[str] = None,
    ) -> ChatResponse:
        return ChatResponse(
            user_ref=request.user_ref,
            reply=_SAFE_FALLBACK_REPLY,
            finish_reason=f"{stage}_safety_blocked",
            safety_blocked=True,
            prompt_version=prompt_version,
            request_id=correlation_id,
            metadata={"safety_stage": stage},
        )

    async def analyze_chat_for_assessment(
        self,
        history: list,
    ) -> dict:
        """Analyze chat history to generate an EQ assessment."""
        
        system_prompt = (
            "You are an expert EQ evaluator. Review the user's chat history and evaluate their emotional intelligence.\n"
            "You must assign a score between 0 and 100 for each of these 6 competencies:\n"
            "SELF_MANAGEMENT, INTERPERSONAL_MANAGEMENT, STRESS_MANAGEMENT, SPIRIT_MANAGEMENT, EXECUTIVE_FUNCTION, DECISION_MAKING.\n"
            "You must also assign an ai_priority rank from 1 to 6 for these competencies (1 being the most urgent area for growth).\n"
            "You MUST output strictly in the following JSON format:\n"
            '{"results": [{"competency": "SELF_MANAGEMENT", "score": 65.0, "ai_priority": 1}, ...]}'
        )
        
        messages = [LLMMessage(role="system", content=system_prompt)]
        
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append(LLMMessage(role=role, content=content))
        
        result = await self._provider.complete_json(messages)
        return result.structured or {}



__all__ = ["ChatService", "DEFAULT_LOCALE"]
