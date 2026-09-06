"""
Chatbot data contracts.

Statelessness
-------------
The AI service holds no conversation memory. Django supplies the full turn
history and all user/journey/progress context on every request, and owns the
source of truth. Nothing here models stored state.

Security posture
----------------
``ChatMessage.role`` accepts only ``user`` and ``assistant``. The ``system``
role is deliberately NOT accepted from the backend: system and developer
instructions are internal to this service, and allowing a caller to inject a
system turn would be a prompt-injection vector.

Context blocks are structurally open (``Dict[str, Any]``) because the Django
context contract has not been supplied. They are typed as data the model may
read, never as instructions — grounding enforcement belongs to the chatbot
layer (Phase 8), not to these schemas.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import ConfigDict, Field, model_validator

from Apps.ai.schemas.common import (
    ExternalRef,
    LocaleTag,
    StrictModel,
    VersionedRequest,
    VersionedResponse,
)

#: Roles the backend is permitted to send. ``system`` is intentionally absent.
ChatRole = Literal["user", "assistant"]


class ChatMessage(StrictModel):
    """A single prior turn in the conversation, supplied by Django."""

    role: ChatRole = Field(
        ..., description="Turn author. Only 'user' and 'assistant' are accepted."
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Turn text. Treated as untrusted data, never as instructions.",
    )


class ChatContext(StrictModel):
    """Read-only context supplied by Django for grounding the reply.

    Every block is optional and structurally open pending the backend
    contract. The chatbot may only make claims that are supported by what
    appears here; it must never fabricate progress or journey state.
    """

    journey: Dict[str, Any] = Field(
        default_factory=dict, description="Journey context supplied by Django."
    )
    competency: Dict[str, Any] = Field(
        default_factory=dict, description="Competency context supplied by Django."
    )
    ability: Dict[str, Any] = Field(
        default_factory=dict, description="Ability context supplied by Django."
    )
    progress: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Progress context supplied by Django. The AI service never infers "
            "or invents progress that is absent here."
        ),
    )


class ChatRequest(VersionedRequest):
    """A single chatbot turn requested by Django."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_ref": "django-user-48213",
                    "message": (
                        "I keep losing my temper in meetings. Any suggestions?"
                    ),
                    "history": [
                        {
                            "role": "user",
                            "content": (
                                "I want to work on staying calm under pressure."
                            ),
                        },
                        {
                            "role": "assistant",
                            "content": (
                                "Let's focus on noticing early signs of "
                                "frustration this week."
                            ),
                        },
                    ],
                    "context": {
                        "journey": {"week": 3, "focus": "competency_1"},
                        "competency": {"code": "competency_1", "score": 6.4},
                        "ability": {"code": "ability_1", "score": 5.2},
                        "progress": {
                            "sessions_completed": 6,
                            "streak_days": 4,
                        },
                    },
                    "locale": "en-GB",
                    "request_id": "django-req-9c8b7a6f",
                }
            ]
        }
    )

    user_ref: ExternalRef = Field(
        ..., description="Opaque backend user reference, used only for correlation."
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="The user's current message. Untrusted input.",
    )
    history: List[ChatMessage] = Field(
        default_factory=list,
        max_length=100,
        description=(
            "Prior turns in chronological order, oldest first. Supplied by "
            "Django because the AI service stores no conversation state."
        ),
    )
    context: ChatContext = Field(
        default_factory=ChatContext,
        description="Grounding context supplied by Django.",
    )
    locale: Optional[LocaleTag] = Field(
        default=None, description="BCP-47 locale tag for the reply."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for backend-supplied context.",
    )

    @model_validator(mode="after")
    def _validate_message_not_blank(self) -> "ChatRequest":
        if not self.message.strip():
            raise ValueError("message must not be blank")
        return self


class ChatResponse(VersionedResponse):
    """Chatbot reply returned to Django."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": "django-req-9c8b7a6f",
                    "user_ref": "django-user-48213",
                    "reply": (
                        "It sounds like meetings are a real trigger for you "
                        "right now. One small thing to try this week: the "
                        "moment you notice your jaw or shoulders tighten, "
                        "pause for a slow breath before responding. What "
                        "usually happens right before you feel that "
                        "frustration build?"
                    ),
                    "finish_reason": "stop",
                    "safety_blocked": False,
                    "prompt_version": "2.0",
                    "metadata": {"provider": "openai", "model": "gpt-4o-mini"},
                }
            ]
        }
    )

    user_ref: ExternalRef = Field(
        ..., description="Correlation reference echoed from the request."
    )
    reply: str = Field(
        ...,
        max_length=8000,
        description="Validated assistant reply. Never raw, unvalidated model output.",
    )
    finish_reason: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Why generation stopped (e.g. 'stop', 'length', 'filtered').",
    )
    safety_blocked: bool = Field(
        default=False,
        description="True when the reply was withheld or replaced by a safety control.",
    )
    prompt_version: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=32,
        description=(
            "Version of the prompt template used, for reproducibility. The "
            "prompt text itself is never exposed."
        ),
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Open extension point for non-authoritative annotations.",
    )


__all__ = [
    "ChatRole",
    "ChatMessage",
    "ChatContext",
    "ChatRequest",
    "ChatResponse",
]
