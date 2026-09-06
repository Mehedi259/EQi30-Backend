"""
Canonical EQi-30 ability definitions.

Each ability belongs to exactly one competency, expressed structurally: an
``Ability`` carries a single ``competency_code``, so multi-parenting is
unrepresentable rather than merely discouraged. Referential integrity against
the competency set is enforced by ``app.domain.Taxonomy``.

As with competencies, an ability carries identity only — no weight, no
reverse-scoring flag, no scale and no threshold.
"""

from typing import Annotated, Tuple

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from Apps.ai.domain.competencies import CompetencyCode

#: The EQi-30 model defines exactly this many abilities in total.
ABILITY_COUNT = 30

#: An ability identifier. Format hygiene only.
AbilityCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_\-.]+$",
    ),
]


class Ability(BaseModel):
    """One of the thirty EQi-30 abilities, owned by exactly one competency."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    code: AbilityCode = Field(
        ..., description="Stable ability identifier from the approved specification."
    )
    name: str = Field(
        ..., min_length=1, max_length=128, description="Human-readable ability name."
    )
    competency_code: CompetencyCode = Field(
        ...,
        description=(
            "Code of the single competency this ability belongs to. A single "
            "scalar field is what makes 'exactly one competency' structural."
        ),
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
# The thirty canonical abilities and their competency assignments are defined
# by the approved EQi-30 project specification, which has not been supplied to
# this repository.
#
# Note: the only EQi taxonomy present on this machine is the prototype at
# ../eqi30-ai-service/app/data/knowledge_graph.json, which defines 40
# abilities (6/8/5/7/7/7 per competency) — not 30. Reducing 40 to 30 would
# require deleting ten abilities and reassigning the rest, which is a
# psychometric decision this service must not make.
#
# To complete the taxonomy, add the thirty approved Ability records below.
# Count, uniqueness and competency referential integrity are already enforced
# and tested.
#
ABILITY_RECORDS: Tuple[Ability, ...] = ()


__all__ = [
    "ABILITY_COUNT",
    "AbilityCode",
    "Ability",
    "ABILITY_RECORDS",
]
