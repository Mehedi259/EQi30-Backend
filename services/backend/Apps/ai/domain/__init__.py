"""
Canonical EQi-30 domain taxonomy.

This package is the single source of truth consumed by:

* assessment              — validating submitted item/ability references
* recommendation          — resolving and ranking competencies
* journey recommendation  — resolving ability references
* chatbot context         — validating Django-supplied competency/ability codes

Enforced invariants
-------------------
1. exactly ``COMPETENCY_COUNT`` (6) competencies
2. competency codes are unique
3. exactly ``ABILITY_COUNT`` (30) abilities
4. ability codes are unique
5. every ability belongs to exactly one competency, and that competency exists
6. every competency owns at least one ability

Invariants are checked when a ``Taxonomy`` is constructed, so an incomplete or
malformed taxonomy fails immediately rather than producing wrong answers
downstream. No scoring, weighting or psychometric logic lives here.
"""

from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, List, Sequence, Tuple

from rest_framework import status

from Apps.ai.core.exceptions import AppException
from Apps.ai.domain.abilities import ABILITY_COUNT, ABILITY_RECORDS, Ability, AbilityCode
from Apps.ai.domain.competencies import (
    COMPETENCY_COUNT,
    COMPETENCY_RECORDS,
    Competency,
    CompetencyCode,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TaxonomyError(AppException):
    """Base class for taxonomy failures."""


class TaxonomySpecificationMissing(TaxonomyError):
    """Raised when the canonical taxonomy has not been supplied."""

    def __init__(self, message: str = "EQi-30 taxonomy has not been specified"):
        super().__init__(
            message=message,
            code="TAXONOMY_NOT_SPECIFIED",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class TaxonomyInvariantError(TaxonomyError):
    """Raised when the supplied taxonomy violates a structural invariant."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="TAXONOMY_INVARIANT_VIOLATION",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class UnknownCompetencyError(TaxonomyError):
    """Raised when a competency code is not part of the canonical taxonomy."""

    def __init__(self, code: str):
        super().__init__(
            message=f"Unknown competency code: {code!r}",
            code="UNKNOWN_COMPETENCY",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"competency_code": code},
        )


class UnknownAbilityError(TaxonomyError):
    """Raised when an ability code is not part of the canonical taxonomy."""

    def __init__(self, code: str):
        super().__init__(
            message=f"Unknown ability code: {code!r}",
            code="UNKNOWN_ABILITY",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details={"ability_code": code},
        )


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


class Taxonomy:
    """An immutable, validated view of the canonical EQi-30 taxonomy."""

    def __init__(
        self,
        competencies: Sequence[Competency],
        abilities: Sequence[Ability],
        *,
        expected_competency_count: int = COMPETENCY_COUNT,
        expected_ability_count: int = ABILITY_COUNT,
    ) -> None:
        self._competencies: Tuple[Competency, ...] = tuple(competencies)
        self._abilities: Tuple[Ability, ...] = tuple(abilities)
        self._expected_competency_count = expected_competency_count
        self._expected_ability_count = expected_ability_count

        self._validate()

        self._competency_by_code: Dict[str, Competency] = {
            c.code: c for c in self._competencies
        }
        self._ability_by_code: Dict[str, Ability] = {a.code: a for a in self._abilities}
        self._abilities_by_competency: Dict[str, Tuple[Ability, ...]] = {
            c.code: tuple(a for a in self._abilities if a.competency_code == c.code)
            for c in self._competencies
        }

    # --- invariants --------------------------------------------------------

    def _validate(self) -> None:
        if not self._competencies and not self._abilities:
            raise TaxonomySpecificationMissing()

        self._require_count(
            self._competencies, self._expected_competency_count, "competencies"
        )
        self._require_unique([c.code for c in self._competencies], "competency code")

        self._require_count(
            self._abilities, self._expected_ability_count, "abilities"
        )
        self._require_unique([a.code for a in self._abilities], "ability code")

        competency_codes = {c.code for c in self._competencies}
        orphans = sorted(
            {a.code for a in self._abilities if a.competency_code not in competency_codes}
        )
        if orphans:
            raise TaxonomyInvariantError(
                "abilities reference unknown competencies: " + ", ".join(orphans)
            )

        owned = {a.competency_code for a in self._abilities}
        empty = sorted(competency_codes - owned)
        if empty:
            raise TaxonomyInvariantError(
                "competencies with no abilities: " + ", ".join(empty)
            )

    @staticmethod
    def _require_count(items: Sequence[object], expected: int, label: str) -> None:
        if len(items) != expected:
            raise TaxonomyInvariantError(
                f"expected exactly {expected} {label}, got {len(items)}"
            )

    @staticmethod
    def _require_unique(codes: Sequence[str], label: str) -> None:
        seen: set = set()
        duplicates: List[str] = []
        for code in codes:
            if code in seen and code not in duplicates:
                duplicates.append(code)
            seen.add(code)
        if duplicates:
            raise TaxonomyInvariantError(
                f"duplicate {label}: " + ", ".join(sorted(duplicates))
            )

    # --- accessors ---------------------------------------------------------

    @property
    def competencies(self) -> Tuple[Competency, ...]:
        return self._competencies

    @property
    def abilities(self) -> Tuple[Ability, ...]:
        return self._abilities

    @property
    def competency_codes(self) -> FrozenSet[str]:
        return frozenset(self._competency_by_code)

    @property
    def ability_codes(self) -> FrozenSet[str]:
        return frozenset(self._ability_by_code)

    def has_competency(self, code: str) -> bool:
        return code in self._competency_by_code

    def has_ability(self, code: str) -> bool:
        return code in self._ability_by_code

    def competency(self, code: str) -> Competency:
        try:
            return self._competency_by_code[code]
        except KeyError:
            raise UnknownCompetencyError(code) from None

    def ability(self, code: str) -> Ability:
        try:
            return self._ability_by_code[code]
        except KeyError:
            raise UnknownAbilityError(code) from None

    def abilities_for(self, competency_code: str) -> Tuple[Ability, ...]:
        if competency_code not in self._competency_by_code:
            raise UnknownCompetencyError(competency_code)
        return self._abilities_by_competency[competency_code]

    def competency_of(self, ability_code: str) -> Competency:
        return self.competency(self.ability(ability_code).competency_code)

    # --- bulk validation (chatbot / request context) -----------------------

    def validate_competency_codes(self, codes: Iterable[str]) -> None:
        """Raise ``UnknownCompetencyError`` on the first unrecognised code."""
        for code in codes:
            if code not in self._competency_by_code:
                raise UnknownCompetencyError(code)

    def validate_ability_codes(self, codes: Iterable[str]) -> None:
        """Raise ``UnknownAbilityError`` on the first unrecognised code."""
        for code in codes:
            if code not in self._ability_by_code:
                raise UnknownAbilityError(code)


@lru_cache(maxsize=1)
def get_taxonomy() -> Taxonomy:
    """Return the validated canonical taxonomy.

    Raises ``TaxonomySpecificationMissing`` until the approved specification
    has been supplied in :mod:`app.domain.competencies` and
    :mod:`app.domain.abilities`.
    """
    return Taxonomy(COMPETENCY_RECORDS, ABILITY_RECORDS)


def is_taxonomy_specified() -> bool:
    """True once canonical records have been supplied (does not validate them)."""
    return bool(COMPETENCY_RECORDS) or bool(ABILITY_RECORDS)


__all__ = [
    "Competency",
    "CompetencyCode",
    "COMPETENCY_COUNT",
    "COMPETENCY_RECORDS",
    "Ability",
    "AbilityCode",
    "ABILITY_COUNT",
    "ABILITY_RECORDS",
    "Taxonomy",
    "TaxonomyError",
    "TaxonomySpecificationMissing",
    "TaxonomyInvariantError",
    "UnknownCompetencyError",
    "UnknownAbilityError",
    "get_taxonomy",
    "is_taxonomy_specified",
]
