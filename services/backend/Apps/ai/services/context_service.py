"""
Context rendering service for the EQi-30 chatbot.

Transforms the Django-supplied ``ChatRequest`` (open, structurally-defined
context dicts, plus the full conversation history) into the bounded,
deterministic inputs the prompt architecture (``app/prompts/chat.py``) and
provider abstraction (``app/providers/``) require.

Persistence / statelessness
----------------------------
This service performs **no I/O**: no database query, no cache read, no call
back into Django. It is a pure, deterministic function of the
``ChatRequest`` it is given — the same request always renders the same
context text and the same trimmed history. It never invents, infers, or
supplements any user information, progress, or journey state beyond what
was explicitly supplied; an empty context block renders as an honest "none
supplied" marker, never as fabricated content.

Conversation context limits
----------------------------
Django's wire contract already caps ``history`` at 100 turns
(``ChatRequest.history``). This service applies a further, service-owned
limit — ``MAX_HISTORY_TURNS`` — because "how much context the AI service
will actually use" is a distinct concern from "how much Django is willing to
send": even within an allowed 100-turn payload, only the most recent turns
are useful to a single-turn coaching reply, and forwarding all of them would
inflate token cost with no benefit. Older turns are dropped outright, never
summarised — summarising would risk fabricating content that was never
actually said.

Each context block (journey / competency / ability / progress) is rendered
as deterministic JSON text (``sort_keys=True``, so key ordering never
affects output) and capped to ``MAX_CONTEXT_BLOCK_CHARS``. The exact shape
of each block is not defined by the (not yet supplied) backend context
contract — see ``app/schemas/chat.py`` — so this service treats every block
as an opaque, structurally-open payload: it extracts nothing from it,
interprets nothing, and never assumes a particular key exists.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from pydantic import BaseModel, ConfigDict

from Apps.ai.providers.base import LLMMessage
from Apps.ai.schemas.chat import ChatContext, ChatMessage

#: Maximum number of prior turns forwarded to the LLM, keeping the most
#: recent ones. A service-owned limit distinct from the wire schema's
#: structural cap of 100 — see module docstring.
MAX_HISTORY_TURNS = 20

#: Maximum characters per rendered context block before truncation.
MAX_CONTEXT_BLOCK_CHARS = 2000

_TRUNCATION_MARKER = "...[truncated]"
_EMPTY_CONTEXT_TEXT = "(none supplied)"


class RenderedChatContext(BaseModel):
    """Deterministic, bounded text rendering of a ``ChatContext``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    journey_context: str
    competency_context: str
    ability_context: str
    progress_context: str


class ContextService:
    """Renders Django-supplied chat context into prompt/provider-ready inputs."""

    def render_context(self, context: ChatContext) -> RenderedChatContext:
        """Render each context block deterministically, with a size cap."""
        return RenderedChatContext(
            journey_context=self._render_block(context.journey),
            competency_context=self._render_block(context.competency),
            ability_context=self._render_block(context.ability),
            progress_context=self._render_block(context.progress),
        )

    def render_history(self, history: Sequence[ChatMessage]) -> List[LLMMessage]:
        """Return the most recent ``MAX_HISTORY_TURNS`` turns as ``LLMMessage``s.

        Older turns are dropped, never summarised: summarising risks
        fabricating content that was never actually part of the
        conversation.
        """
        trimmed = list(history)[-MAX_HISTORY_TURNS:]
        return [LLMMessage(role=turn.role, content=turn.content) for turn in trimmed]

    @staticmethod
    def _render_block(data: Dict[str, Any]) -> str:
        if not data:
            return _EMPTY_CONTEXT_TEXT
        rendered = json.dumps(data, sort_keys=True, ensure_ascii=False)
        if len(rendered) > MAX_CONTEXT_BLOCK_CHARS:
            cutoff = MAX_CONTEXT_BLOCK_CHARS - len(_TRUNCATION_MARKER)
            rendered = rendered[:cutoff] + _TRUNCATION_MARKER
        return rendered


__all__ = [
    "ContextService",
    "RenderedChatContext",
    "MAX_HISTORY_TURNS",
    "MAX_CONTEXT_BLOCK_CHARS",
]
