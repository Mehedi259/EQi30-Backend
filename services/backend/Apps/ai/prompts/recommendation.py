"""
Competency-recommendation rationale prompt builder.

SCOPE: this prompt never decides or adjusts ``ai_priority``. Priority
ranking is owned exclusively by the deterministic, versioned
``RecommendationStrategy`` pipeline (see ``app/domain/recommendation.py``).
This builder's only job is narrating a rationale for an already-decided
priority — the ranking itself is read-only input data.

``user_priority`` is Django's alone. This prompt never receives it, never
produces it, and never references it — see ``_SAFETY_CONSTRAINTS`` below.

DRAFT — architecture scaffolding only. Wording here is placeholder text, not
reviewed/approved production copy.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from Apps.ai.prompts import PromptBuilder, PromptRegistry, PromptVariable

_REQUIRED_VARIABLES: Tuple[PromptVariable, ...] = (
    PromptVariable(
        name="competency_code",
        description="Opaque competency identifier the rationale is for.",
        required=True,
    ),
    PromptVariable(
        name="ai_priority",
        description=(
            "Already-decided AI priority rank for this competency, as text "
            "(e.g. '1'). Supplied by the calling service — this prompt does "
            "not decide priority."
        ),
        required=True,
    ),
    PromptVariable(
        name="context",
        description="Optional supplied context relevant to the rationale.",
        required=False,
        default="(none supplied)",
    ),
)

_SAFETY_CONSTRAINTS: Tuple[str, ...] = (
    "Never propose or imply a different priority than the one supplied.",
    "Never mention or imply user_priority — this service neither receives "
    "nor produces it.",
    "Never claim assessment data beyond what is supplied in context.",
)


class CompetencyRationalePromptV1(PromptBuilder):
    """Version 1.0 of the competency-recommendation rationale prompt."""

    @property
    def prompt_id(self) -> str:
        return "recommendation.rationale"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def purpose(self) -> str:
        return (
            "Produce a short rationale explaining an already-decided "
            "competency ai_priority. Does not decide or alter the ranking."
        )

    @property
    def required_variables(self) -> Tuple[PromptVariable, ...]:
        return _REQUIRED_VARIABLES

    @property
    def output_requirements(self) -> str:
        return (
            "One short paragraph of plain prose. Must not restate or imply "
            "a numeric priority different from the supplied ai_priority."
        )

    @property
    def safety_constraints(self) -> Tuple[str, ...]:
        return _SAFETY_CONSTRAINTS

    def _build(self, variables: Dict[str, Any]) -> Tuple[str, str]:
        rules = "\n".join(f"- {rule}" for rule in self.safety_constraints)
        system_text = (
            "You write short rationales explaining an already-decided "
            "competency priority ranking.\n"
            f"Rules:\n{rules}"
        )
        context = variables.get("context") or "(none supplied)"
        user_text = (
            f"Competency: {variables['competency_code']}\n"
            f"AI priority (already decided, do not change): "
            f"{variables['ai_priority']}\n"
            f"Additional context: {context}\n\n"
            "Write a short rationale for this priority."
        )
        return system_text, user_text


RECOMMENDATION_RATIONALE_REGISTRY = PromptRegistry(prompt_id="recommendation.rationale")
RECOMMENDATION_RATIONALE_REGISTRY.register(
    CompetencyRationalePromptV1(), set_default=True
)


__all__ = ["CompetencyRationalePromptV1", "RECOMMENDATION_RATIONALE_REGISTRY"]
