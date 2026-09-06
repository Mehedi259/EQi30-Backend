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
#
# PENDING APPROVED SPECIFICATION.
#
# The six canonical competencies are defined by the approved EQi-30 project
# specification, which has not been supplied to this repository (docs/ are
# empty). Populating this tuple with invented competencies would fabricate the
# product's canonical taxonomy, which CLAUDE.md forbids.
#
# To complete the taxonomy, add the six approved Competency records below.
# Every invariant (count, uniqueness, referential integrity with abilities) is
# already enforced and tested, so a malformed or incomplete drop-in fails
# immediately and loudly rather than silently propagating.
#
COMPETENCY_RECORDS: Tuple[Competency, ...] = ()


__all__ = [
    "COMPETENCY_COUNT",
    "CompetencyCode",
    "Competency",
    "COMPETENCY_RECORDS",
]
