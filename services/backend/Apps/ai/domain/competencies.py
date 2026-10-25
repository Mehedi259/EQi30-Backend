"""
Canonical EQi-30 competency definitions.

This module is the single source of truth for *what a competency is* and how
many there are. It is consumed by assessment, recommendation, journey
recommendation and chatbot context validation via ``app.domain.get_taxonomy``.

No psychometric methodology lives here: a ``Competency`` carries identity and
description only. It has no weight, no scale, no threshold and no scoring
behaviour.
"""

from typing import Annotated, Tuple

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

#: The EQi-30 model defines exactly this many competencies.
COMPETENCY_COUNT = 6

#: A competency identifier. Format hygiene only — no naming convention is
#: imposed, because the codes come from the approved specification.
CompetencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_\-.]+$",
    ),
]


class Competency(BaseModel):
    """One of the six EQi-30 competencies.

    Immutable: the taxonomy is a fixed reference structure, not runtime state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    code: CompetencyCode = Field(
        ..., description="Stable competency identifier from the approved specification."
    )
    name: str = Field(
        ..., min_length=1, max_length=128, description="Human-readable competency name."
    )
    description: str = Field(
        default="", max_length=2000, description="Optional descriptive text."
    )


# ---------------------------------------------------------------------------
# Canonical records
# ---------------------------------------------------------------------------
COMPETENCY_RECORDS: Tuple[Competency, ...] = (
    Competency(
        code="SELF_MANAGEMENT",
        name="Self-Management",
        description="The operational engine of your inner life: understanding, regulating, and directing your personal emotional states, boundaries, and intrinsic potential.",
    ),
    Competency(
        code="INTERPERSONAL_MANAGEMENT",
        name="Interpersonal Management",
        description="The bridge to the outside world: building constructive relationships, communicating effectively, navigating conflicts, and empathizing with others.",
    ),
    Competency(
        code="STRESS_MANAGEMENT",
        name="Stress Management",
        description="Your shock absorber in an unpredictable world: withstanding pressure, maintaining emotional balance, adapting thinking flexibly, and staying resilient.",
    ),
    Competency(
        code="SPIRIT_MANAGEMENT",
        name="Spirit Management",
        description="Your internal compass and vitality engine: connecting with purpose, maintaining authentic energy, cultivating community, and finding meaning.",
    ),
    Competency(
        code="EXECUTIVE_FUNCTION",
        name="Executive Function",
        description="The CEO of your mind: planning, prioritizing, focusing attention, sustaining motivation, and organizing daily life into tangible action.",
    ),
    Competency(
        code="DECISION_MAKING",
        name="Decision Making",
        description="Your reality-testing apparatus: evaluating circumstances objectively, regulating impulses, conceptualizing ideas, and solving complex problems.",
    ),
)


__all__ = [
    "COMPETENCY_COUNT",
    "CompetencyCode",
    "Competency",
    "COMPETENCY_RECORDS",
]
