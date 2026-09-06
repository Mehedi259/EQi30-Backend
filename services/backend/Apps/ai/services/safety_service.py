"""
Safety checks for the EQi-30 chatbot: input-stage prompt-injection/
context-poisoning screening and output-stage validation.

Both checks are deterministic, pattern-based heuristics — not the sole line
of defense. The primary defense against prompt injection is architectural:
``app/prompts/chat.py`` already delimits the user's message and every
context block as data, never as instructions, and instructs the model to
ignore embedded commands. This service adds a second, code-level layer that
can act *before* a suspicious message is ever sent to the LLM (input check)
and *after* the model replies, before that reply is trusted (output check) —
consistent with "never trust raw LLM output" and with using structured
validation rather than relying on prompt instructions alone.

``check_input`` screens three sources: the current message, prior
``user``-role history turns, and the supplied ``ChatContext`` blocks
(journey/competency/ability/progress) — the last of these is context-
poisoning protection, since Django-supplied context is not implicitly
trusted just because it did not come from the end user directly.

``check_output`` screens for an empty/oversized reply, leaked system-prompt
text, unperformed-action claims, and — when no grounding context was
supplied at all for the turn — a specific progress/score/completion claim,
which in that specific condition can only be hallucinated.

Neither check raises an exception. A flagged result is not the caller's
fault — there is nothing wrong with the HTTP request — so blocking is
expressed by the caller (``app/services/chat_service.py``) as a normal,
successful ``ChatResponse`` with ``safety_blocked=True``, never as an error
status.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

from Apps.ai.schemas.chat import ChatContext, ChatMessage

#: Case-insensitive fragments associated with attempts to override or
#: extract the system/developer instructions. Heuristic and not exhaustive —
#: a defense-in-depth layer alongside the prompt's own data/instruction
#: delimiting, not a replacement for it.
_INJECTION_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore (all )?(the )?(previous|prior|above) instructions",
        r"disregard (all )?(the )?(previous|prior|above) (instructions|rules)",
        r"reveal (your |the )?(system|developer) prompt",
        r"(show|print|output|repeat) (me )?(your |the )?(system|developer) prompt",
        r"what (are|is) your (system|developer) (prompt|instructions)",
        r"you are now (in )?(developer|jailbreak|dan) mode",
        r"act as (if you (are|were)|an?) (unrestricted|unfiltered|jailbroken)",
        r"pretend (you have no|there are no) (rules|restrictions|guidelines)",
    )
)

#: Case-insensitive phrases claiming a side-effecting action the AI service
#: does not have the ability to perform. Heuristic and not exhaustive.
_UNPERFORMED_ACTION_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"i(?:'ve| have) (?:just )?(saved|updated|scheduled|sent|deleted|"
        r"created|added|completed|logged|recorded|booked)",
        r"i(?:'ll| will) (?:now )?(save|update|schedule|send|delete|create|"
        r"add|log|record|book) (that|this|it) for you",
    )
)

#: Case-insensitive phrases claiming specific progress, an assessment
#: score, or a completion count. Only checked when NO grounding context
#: (journey/competency/ability/progress) was supplied at all — the one case
#: where any such claim is, by construction, unsupported by anything the
#: caller gave the model. Heuristic and not exhaustive; a structural
#: complement to (not a replacement for) the prompt's own "never state
#: progress beyond this" instruction.
_UNGROUNDED_CLAIM_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b\d+(?:\.\d+)?\s*(?:of|out of|/)\s*\d+(?:\.\d+)?\b",
        r"\b\d+(?:\.\d+)?\s*%",
        r"\b\d+\s*(?:day|days|session|sessions)\s+(?:streak|in a row)\b",
        r"\b(?:completed|finished)\s+\d+\b",
        r"\byour\s+[\w\s]{0,20}?\s*score\s+(?:is|was)\s+\d+(?:\.\d+)?\b",
    )
)

#: Mirrors ``ChatResponse.reply``'s ``max_length`` (app/schemas/chat.py).
#: See tests/unit/test_chat_contracts.py for the automated drift guard.
MAX_REPLY_LENGTH = 8000

#: Minimum contiguous character run checked when scanning a reply for
#: leaked system-prompt text.
_SYSTEM_LEAK_MIN_CHUNK = 40

#: Names of the ChatContext blocks scanned for context poisoning.
_CONTEXT_BLOCK_NAMES: Tuple[str, ...] = (
    "journey",
    "competency",
    "ability",
    "progress",
)


class SafetyCheckResult(BaseModel):
    """Outcome of a single safety screening pass."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    flagged: bool
    reasons: Tuple[str, ...] = ()


class SafetyService:
    """Deterministic input/output safety screening for chat turns."""

    def check_input(
        self,
        message: str,
        history: Sequence[ChatMessage] = (),
        context: Optional[ChatContext] = None,
    ) -> SafetyCheckResult:
        """Screen the message, prior user turns, and supplied context for
        injection attempts.

        Only ``user``-authored history is scanned: injection is about
        attacker-controlled input, and the assistant's own prior replies are
        not attacker-controlled. ``context`` (journey/competency/ability/
        progress) is scanned too — it is supplied by Django, not typed by
        the end user, but a compromised or careless upstream caller could
        still forward attacker-influenced text through it (e.g. a free-text
        field embedded in journey data), so it is not implicitly trusted
        either. This is context-poisoning protection: structured scanning,
        not reliance on the prompt's own "treat context as data" instruction
        alone.
        """
        reasons: List[str] = []
        for label, text in self._input_texts(message, history, context):
            match = self._first_match(_INJECTION_PATTERNS, text)
            if match:
                reasons.append(f"possible prompt injection in {label}: {match!r}")
        return SafetyCheckResult(flagged=bool(reasons), reasons=tuple(reasons))

    def check_output(
        self,
        reply: str,
        *,
        system_prompt: str,
        grounding_context_supplied: bool = True,
    ) -> SafetyCheckResult:
        """Validate a provider reply before it is trusted and returned.

        ``grounding_context_supplied`` should be ``False`` when none of the
        journey/competency/ability/progress context blocks were supplied for
        this turn. In that specific case, a reply containing a specific
        progress/score/completion claim is flagged: there is nothing in the
        request the claim could possibly be grounded in, so it is either
        hallucinated or reused stale context from elsewhere — never
        supplied information.
        """
        reasons: List[str] = []

        stripped = reply.strip()
        if not stripped:
            reasons.append("reply was empty")

        if len(reply) > MAX_REPLY_LENGTH:
            reasons.append(
                f"reply exceeded the maximum length of {MAX_REPLY_LENGTH} characters"
            )

        if stripped and self._leaks_system_prompt(reply, system_prompt):
            reasons.append(
                "reply appears to contain system/developer instruction text"
            )

        action_match = self._first_match(_UNPERFORMED_ACTION_PATTERNS, reply)
        if action_match:
            reasons.append(f"reply claims an unperformed action: {action_match!r}")

        if not grounding_context_supplied:
            claim_match = self._first_match(_UNGROUNDED_CLAIM_PATTERNS, reply)
            if claim_match:
                reasons.append(
                    f"reply states a specific progress/score claim "
                    f"({claim_match!r}) though no journey, competency, "
                    f"ability, or progress context was supplied"
                )

        return SafetyCheckResult(flagged=bool(reasons), reasons=tuple(reasons))

    @staticmethod
    def _input_texts(
        message: str,
        history: Sequence[ChatMessage],
        context: Optional[ChatContext],
    ) -> Iterable[Tuple[str, str]]:
        yield "the current message", message
        for index, turn in enumerate(history):
            if turn.role == "user":
                yield f"history[{index}]", turn.content
        if context is not None:
            for block_name in _CONTEXT_BLOCK_NAMES:
                data: Dict[str, Any] = getattr(context, block_name)
                if data:
                    yield f"context.{block_name}", json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _first_match(patterns: Sequence[re.Pattern], text: str) -> Optional[str]:
        for pattern in patterns:
            found = pattern.search(text)
            if found:
                return found.group(0)
        return None

    @staticmethod
    def _leaks_system_prompt(
        reply: str, system_prompt: str, *, min_chunk: int = _SYSTEM_LEAK_MIN_CHUNK
    ) -> bool:
        """True if a contiguous chunk of the system prompt appears in the reply."""
        normalized_reply = reply.lower()
        normalized_system = system_prompt.lower()
        if len(normalized_system) < min_chunk:
            return False
        for start in range(0, len(normalized_system) - min_chunk + 1, min_chunk):
            chunk = normalized_system[start : start + min_chunk]
            if chunk in normalized_reply:
                return True
        return False


__all__ = ["SafetyCheckResult", "SafetyService", "MAX_REPLY_LENGTH"]
