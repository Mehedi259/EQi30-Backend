"""
Journey-item narrative prompt builder.

SCOPE: this prompt never decides ranking, journey content, or structure.
That is owned exclusively by the deterministic, versioned
``JourneyRecommendationStrategy`` pipeline (see ``app/domain/journey.py``).
This builder's only job is narrating an already-ranked journey item.

The user-selection taxonomy is not finalized (see ``app/domain/journey.py``,
``JourneySelectionEnvelope``). No taxonomy field names are referenced here:
``selection_summary`` is an opaque, pre-formatted text the calling service is
responsible for producing from whatever taxonomy is eventually approved.

DRAFT — architecture scaffolding only. Wording here is placeholder text, not
reviewed/approved production copy.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from Apps.ai.prompts import PromptBuilder, PromptRegistry, PromptVariable

_REQUIRED_VARIABLES: Tuple[PromptVariable, ...] = (
    PromptVariable(
        name="reference",
        description="Opaque reference to the already-ranked journey item.",
        required=True,
    ),
    PromptVariable(
        name="rank",
        description="Already-decided 1-based rank for this item, as text.",
        required=True,
    ),
    PromptVariable(
        name="locale",
        description="BCP-47 locale tag the narrative must be written in.",
        required=True,
    ),
    PromptVariable(
        name="selection_summary",
        description=(
            "Optional, pre-formatted opaque text summarising the user's "
            "approved selections, in whatever shape the (not yet finalized) "
            "taxonomy eventually defines. No specific fields are assumed "
            "or invented here."
        ),
        required=False,
        default="(none supplied)",
    ),
)

_SAFETY_CONSTRAINTS: Tuple[str, ...] = (
    "Never propose a different reference or rank than the one supplied.",
    "Never invent journey content, duration, or structure beyond what the "
    "supplied reference and selection_summary imply.",
    "Never assume or invent user-selection taxonomy fields that were not "
    "supplied in selection_summary.",
)


class JourneyItemNarrativePromptV1(PromptBuilder):
    """Version 1.0 of the journey-item narrative prompt."""

    @property
    def prompt_id(self) -> str:
        return "journey.narrative"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def purpose(self) -> str:
        return (
            "Produce a short narrative for an already-ranked journey item. "
            "Does not decide ranking or journey content."
        )

    @property
    def required_variables(self) -> Tuple[PromptVariable, ...]:
        return _REQUIRED_VARIABLES

    @property
    def output_requirements(self) -> str:
        return (
            "One short paragraph of plain prose. Must not restate or imply "
            "a rank different from the supplied rank."
        )

    @property
    def safety_constraints(self) -> Tuple[str, ...]:
        return _SAFETY_CONSTRAINTS

    def _build(self, variables: Dict[str, Any]) -> Tuple[str, str]:
        rules = "\n".join(f"- {rule}" for rule in self.safety_constraints)
        system_text = (
            "You write short narratives for an already-ranked journey "
            "recommendation item.\n"
            f"Rules:\n{rules}"
        )
        selection_summary = variables.get("selection_summary") or "(none supplied)"
        user_text = (
            f"Locale: {variables['locale']}\n"
            f"Journey reference (already ranked, do not change): "
            f"{variables['reference']}\n"
            f"Rank (already decided, do not change): {variables['rank']}\n"
            f"User selection summary: {selection_summary}\n\n"
            "Write a short narrative for this journey item."
        )
        return system_text, user_text


JOURNEY_NARRATIVE_REGISTRY = PromptRegistry(prompt_id="journey.narrative")
JOURNEY_NARRATIVE_REGISTRY.register(JourneyItemNarrativePromptV1(), set_default=True)


__all__ = ["JourneyItemNarrativePromptV1", "JOURNEY_NARRATIVE_REGISTRY"]
