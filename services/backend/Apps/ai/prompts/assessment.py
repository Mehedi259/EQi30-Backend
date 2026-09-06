"""
Assessment-narrative prompt builder.

SCOPE: this prompt never computes, adjusts, or infers a score. Scoring is
owned exclusively by the deterministic, versioned ``ScoringStrategy``
pipeline (see ``app/domain/scoring.py``) and must never be delegated to an
LLM. This builder's only job is turning already-computed, already-validated
competency scores into a plain-language narrative — the numbers themselves
are read-only input data supplied by the caller.

DRAFT — architecture scaffolding only. Wording here is placeholder text, not
reviewed/approved production copy.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from Apps.ai.prompts import PromptBuilder, PromptRegistry, PromptVariable

_REQUIRED_VARIABLES: Tuple[PromptVariable, ...] = (
    PromptVariable(
        name="competency_scores",
        description=(
            "Pre-formatted, read-only text rendering of the already-computed "
            "competency scores (e.g. 'self_management: 6.2/10; ...'). "
            "Supplied by the calling service — this prompt does not compute "
            "scores."
        ),
        required=True,
    ),
    PromptVariable(
        name="locale",
        description="BCP-47 locale tag the narrative must be written in.",
        required=True,
    ),
)

_SAFETY_CONSTRAINTS: Tuple[str, ...] = (
    "Never invent, adjust, round differently, or omit any score present in "
    "the supplied data.",
    "Never introduce a competency, ability, or score that is not present "
    "in the supplied data.",
    "Never phrase the narrative as clinical, diagnostic, or medical advice.",
)


class AssessmentSummaryPromptV1(PromptBuilder):
    """Version 1.0 of the assessment-narrative prompt."""

    @property
    def prompt_id(self) -> str:
        return "assessment.summary"

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def purpose(self) -> str:
        return (
            "Produce a plain-language narrative explaining already-computed "
            "competency scores. Does not compute or alter any score."
        )

    @property
    def required_variables(self) -> Tuple[PromptVariable, ...]:
        return _REQUIRED_VARIABLES

    @property
    def output_requirements(self) -> str:
        return (
            "Plain prose only (no additional structured data, no new "
            "scores). Must reference only the competencies and values "
            "present in the supplied competency_scores text."
        )

    @property
    def safety_constraints(self) -> Tuple[str, ...]:
        return _SAFETY_CONSTRAINTS

    def _build(self, variables: Dict[str, Any]) -> Tuple[str, str]:
        rules = "\n".join(f"- {rule}" for rule in self.safety_constraints)
        system_text = (
            "You write short, plain-language summaries of already-computed "
            "emotional intelligence competency scores.\n"
            f"Rules:\n{rules}"
        )
        user_text = (
            f"Locale: {variables['locale']}\n"
            f"Competency scores (read-only, already computed):\n"
            f"{variables['competency_scores']}\n\n"
            "Write a short narrative summary of these results."
        )
        return system_text, user_text


ASSESSMENT_SUMMARY_REGISTRY = PromptRegistry(prompt_id="assessment.summary")
ASSESSMENT_SUMMARY_REGISTRY.register(AssessmentSummaryPromptV1(), set_default=True)


__all__ = ["AssessmentSummaryPromptV1", "ASSESSMENT_SUMMARY_REGISTRY"]
