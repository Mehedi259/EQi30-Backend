"""
EQi-30 Self-Report Scoring Strategy.

Official psychometric scoring implementation for the EQi-30 Assessment
consisting of 103 items evaluated across 30 abilities grouped into 6 competencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from Apps.ai.domain.scoring import (
    CompetencyScoreResult,
    ScoringInputError,
    ScoringStrategy,
    get_scoring_registry,
)

# 103 Official Assessment Items: (item_id, ability_code, competency_code, is_reverse)
EQI30_ITEMS: Tuple[Tuple[int, str, str, bool], ...] = (
    # --- SELF_MANAGEMENT (Items 1 - 15) ---
    (1, "EMOTIONAL_AWARENESS", "SELF_MANAGEMENT", False),
    (2, "EMOTIONAL_AWARENESS", "SELF_MANAGEMENT", False),
    (3, "EMOTIONAL_AWARENESS", "SELF_MANAGEMENT", False),
    (4, "BOUNDARY_AWARENESS", "SELF_MANAGEMENT", True),
    (5, "BOUNDARY_AWARENESS", "SELF_MANAGEMENT", False),
    (6, "BOUNDARY_AWARENESS", "SELF_MANAGEMENT", True),
    (7, "SELF_CONFIDENCE", "SELF_MANAGEMENT", False),
    (8, "SELF_CONFIDENCE", "SELF_MANAGEMENT", False),
    (9, "SELF_CONFIDENCE", "SELF_MANAGEMENT", True),
    (10, "SELF_ACTUALIZATION", "SELF_MANAGEMENT", False),
    (11, "SELF_ACTUALIZATION", "SELF_MANAGEMENT", False),
    (12, "SELF_ACTUALIZATION", "SELF_MANAGEMENT", True),
    (13, "INDEPENDENCE", "SELF_MANAGEMENT", True),
    (14, "INDEPENDENCE", "SELF_MANAGEMENT", False),
    (15, "INDEPENDENCE", "SELF_MANAGEMENT", True),

    # --- INTERPERSONAL_MANAGEMENT (Items 16 - 30) ---
    (16, "EMPATHY", "INTERPERSONAL_MANAGEMENT", False),
    (17, "EMPATHY", "INTERPERSONAL_MANAGEMENT", True),
    (18, "EMPATHY", "INTERPERSONAL_MANAGEMENT", False),
    (19, "VERBAL_EXPRESSION", "INTERPERSONAL_MANAGEMENT", False),
    (20, "VERBAL_EXPRESSION", "INTERPERSONAL_MANAGEMENT", True),
    (21, "VERBAL_EXPRESSION", "INTERPERSONAL_MANAGEMENT", False),
    (22, "NON_VERBAL_COMMUNICATION", "INTERPERSONAL_MANAGEMENT", False),
    (23, "NON_VERBAL_COMMUNICATION", "INTERPERSONAL_MANAGEMENT", False),
    (24, "NON_VERBAL_COMMUNICATION", "INTERPERSONAL_MANAGEMENT", True),
    (25, "ASSERTIVENESS", "INTERPERSONAL_MANAGEMENT", False),
    (26, "ASSERTIVENESS", "INTERPERSONAL_MANAGEMENT", False),
    (27, "ASSERTIVENESS", "INTERPERSONAL_MANAGEMENT", True),
    (28, "CONFLICT_MANAGEMENT", "INTERPERSONAL_MANAGEMENT", False),
    (29, "CONFLICT_MANAGEMENT", "INTERPERSONAL_MANAGEMENT", True),
    (30, "CONFLICT_MANAGEMENT", "INTERPERSONAL_MANAGEMENT", False),

    # --- STRESS_MANAGEMENT (Items 31 - 45) ---
    (31, "STRESS_TOLERANCE", "STRESS_MANAGEMENT", False),
    (32, "STRESS_TOLERANCE", "STRESS_MANAGEMENT", True),
    (33, "STRESS_TOLERANCE", "STRESS_MANAGEMENT", False),
    (34, "COGNITIVE_FLEXIBILITY", "STRESS_MANAGEMENT", False),
    (35, "COGNITIVE_FLEXIBILITY", "STRESS_MANAGEMENT", False),
    (36, "COGNITIVE_FLEXIBILITY", "STRESS_MANAGEMENT", True),
    (37, "EMOTIONAL_REGULATION", "STRESS_MANAGEMENT", True),
    (38, "EMOTIONAL_REGULATION", "STRESS_MANAGEMENT", False),
    (39, "EMOTIONAL_REGULATION", "STRESS_MANAGEMENT", True),
    (40, "OPTIMISM", "STRESS_MANAGEMENT", False),
    (41, "OPTIMISM", "STRESS_MANAGEMENT", False),
    (42, "OPTIMISM", "STRESS_MANAGEMENT", True),
    (43, "SOCIAL_RESOURCES", "STRESS_MANAGEMENT", False),
    (44, "SOCIAL_RESOURCES", "STRESS_MANAGEMENT", True),
    (45, "SOCIAL_RESOURCES", "STRESS_MANAGEMENT", False),

    # --- SPIRIT_MANAGEMENT (Items 46 - 60) ---
    (46, "BELIEF_INFLUENCE", "SPIRIT_MANAGEMENT", False),
    (47, "BELIEF_INFLUENCE", "SPIRIT_MANAGEMENT", True),
    (48, "BELIEF_INFLUENCE", "SPIRIT_MANAGEMENT", False),
    (49, "CLARITY", "SPIRIT_MANAGEMENT", False),
    (50, "CLARITY", "SPIRIT_MANAGEMENT", False),
    (51, "CLARITY", "SPIRIT_MANAGEMENT", True),
    (52, "ENERGY_AWARENESS", "SPIRIT_MANAGEMENT", False),
    (53, "ENERGY_AWARENESS", "SPIRIT_MANAGEMENT", False),
    (54, "ENERGY_AWARENESS", "SPIRIT_MANAGEMENT", True),
    (55, "COMMUNITY_BUILDING", "SPIRIT_MANAGEMENT", False),
    (56, "COMMUNITY_BUILDING", "SPIRIT_MANAGEMENT", True),
    (57, "COMMUNITY_BUILDING", "SPIRIT_MANAGEMENT", False),
    (58, "MEANING_MAKING", "SPIRIT_MANAGEMENT", False),
    (59, "MEANING_MAKING", "SPIRIT_MANAGEMENT", False),
    (60, "MEANING_MAKING", "SPIRIT_MANAGEMENT", True),

    # --- EXECUTIVE_FUNCTION (Items 61 - 75) ---
    (61, "PLANNING", "EXECUTIVE_FUNCTION", False),
    (62, "PLANNING", "EXECUTIVE_FUNCTION", False),
    (63, "PLANNING", "EXECUTIVE_FUNCTION", True),
    (64, "PRIORITIZING", "EXECUTIVE_FUNCTION", False),
    (65, "PRIORITIZING", "EXECUTIVE_FUNCTION", False),
    (66, "PRIORITIZING", "EXECUTIVE_FUNCTION", True),
    (67, "MOTIVATION", "EXECUTIVE_FUNCTION", False),
    (68, "MOTIVATION", "EXECUTIVE_FUNCTION", True),
    (69, "MOTIVATION", "EXECUTIVE_FUNCTION", False),
    (70, "ATTENTION_SPAN", "EXECUTIVE_FUNCTION", True),
    (71, "ATTENTION_SPAN", "EXECUTIVE_FUNCTION", False),
    (72, "ATTENTION_SPAN", "EXECUTIVE_FUNCTION", True),
    (73, "ORGANIZATION", "EXECUTIVE_FUNCTION", False),
    (74, "ORGANIZATION", "EXECUTIVE_FUNCTION", False),
    (75, "ORGANIZATION", "EXECUTIVE_FUNCTION", True),

    # --- DECISION_MAKING (Items 76 - 103) ---
    (76, "PROCESSING_SPEED", "DECISION_MAKING", False),
    (77, "PROCESSING_SPEED", "DECISION_MAKING", False),
    (78, "PROCESSING_SPEED", "DECISION_MAKING", True),
    (79, "IMPULSE_CONTROL", "DECISION_MAKING", True),
    (80, "IMPULSE_CONTROL", "DECISION_MAKING", False),
    (81, "IMPULSE_CONTROL", "DECISION_MAKING", True),
    (82, "IMPULSE_CONTROL", "DECISION_MAKING", False),
    (83, "REALITY_TESTING", "DECISION_MAKING", False),
    (84, "REALITY_TESTING", "DECISION_MAKING", False),
    (85, "REALITY_TESTING", "DECISION_MAKING", True),
    (86, "ABSTRACTION", "DECISION_MAKING", False),
    (87, "ABSTRACTION", "DECISION_MAKING", False),
    (88, "ABSTRACTION", "DECISION_MAKING", True),
    (89, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (90, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (91, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (92, "PROBLEM_SOLVING", "DECISION_MAKING", True),
    (93, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (94, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (95, "PROBLEM_SOLVING", "DECISION_MAKING", True),
    (96, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (97, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (98, "PROBLEM_SOLVING", "DECISION_MAKING", True),
    (99, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (100, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (101, "PROBLEM_SOLVING", "DECISION_MAKING", False),
    (102, "PROBLEM_SOLVING", "DECISION_MAKING", True),
    (103, "PROBLEM_SOLVING", "DECISION_MAKING", False),
)

ITEM_LOOKUP: Dict[str, Tuple[str, str, bool]] = {}
for item_id, ability, comp, is_rev in EQI30_ITEMS:
    ITEM_LOOKUP[str(item_id)] = (ability, comp, is_rev)


class EQi30ScoringStrategy(ScoringStrategy):
    """Official psychometric scoring methodology for EQi-30 self-report instrument."""

    @property
    def version(self) -> str:
        return "eqi30-self-report-v1"

    @property
    def description(self) -> str:
        return "Approved EQi-30 103-item psychometric assessment scoring strategy."

    def validate_input(
        self, answers: List[dict], instrument_version: str
    ) -> None:
        if not answers:
            raise ScoringInputError("Answers list cannot be empty for EQi-30 scoring.")

        for i, a in enumerate(answers):
            val = a.get("value")
            if val is None:
                raise ScoringInputError(f"Missing response value at index {i}.")
            try:
                num_val = float(val)
                if num_val < 1.0 or num_val > 10.0:
                    raise ScoringInputError(
                        f"Response value {num_val} for item {a.get('item_id')} out of range [1, 10]."
                    )
            except (ValueError, TypeError):
                raise ScoringInputError(f"Invalid non-numeric value '{val}' at index {i}.")

    def compute_scores(
        self, answers: List[dict], instrument_version: str
    ) -> List[CompetencyScoreResult]:
        """Aggregate item scores into 30 ability averages and 6 competency scores (0 - 100)."""
        ability_scores: Dict[str, List[float]] = {}
        competency_abilities: Dict[str, set[str]] = {
            "SELF_MANAGEMENT": set(),
            "INTERPERSONAL_MANAGEMENT": set(),
            "STRESS_MANAGEMENT": set(),
            "SPIRIT_MANAGEMENT": set(),
            "EXECUTIVE_FUNCTION": set(),
            "DECISION_MAKING": set(),
        }

        # Index answers by item_id
        answer_by_id = {str(a.get("item_id")): float(a.get("value", 5.0)) for a in answers}

        for item_id, ability, comp, is_rev in EQI30_ITEMS:
            competency_abilities[comp].add(ability)
            raw = answer_by_id.get(str(item_id), 5.0)
            effective = (11.0 - raw) if is_rev else raw
            ability_scores.setdefault(ability, []).append(effective)

        # Compute average per ability (scale 1.0 - 10.0)
        ability_averages: Dict[str, float] = {
            ability: sum(vals) / len(vals)
            for ability, vals in ability_scores.items()
            if vals
        }

        results: List[CompetencyScoreResult] = []
        ordered_competencies = [
            "SELF_MANAGEMENT",
            "INTERPERSONAL_MANAGEMENT",
            "STRESS_MANAGEMENT",
            "SPIRIT_MANAGEMENT",
            "EXECUTIVE_FUNCTION",
            "DECISION_MAKING",
        ]

        for comp_code in ordered_competencies:
            abilities_in_comp = competency_abilities.get(comp_code, set())
            comp_ability_scores = {
                ab: round(ability_averages.get(ab, 5.0), 2)
                for ab in abilities_in_comp
            }
            if comp_ability_scores:
                comp_avg = sum(comp_ability_scores.values()) / len(comp_ability_scores)
            else:
                comp_avg = 5.0

            # Scale 1-10 average to 0-100 percentage
            comp_score_pct = round(comp_avg * 10.0, 1)

            results.append(
                CompetencyScoreResult(
                    competency_code=comp_code,
                    score=comp_score_pct,
                    scale_min=0.0,
                    scale_max=100.0,
                    ability_scores=comp_ability_scores,
                )
            )

        return results


def register_eqi30_scoring() -> None:
    """Register the approved EQi-30 scoring strategy in the global registry."""
    registry = get_scoring_registry()
    strategy = EQi30ScoringStrategy()
    registry.register(strategy, set_default=True)
