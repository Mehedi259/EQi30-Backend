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
ABILITY_RECORDS: Tuple[Ability, ...] = (
    # SELF_MANAGEMENT (5 abilities)
    Ability(
        code="EMOTIONAL_AWARENESS",
        name="Emotional Awareness",
        competency_code="SELF_MANAGEMENT",
        description="Recognizing, naming, and understanding what you are feeling in the moment and noticing bodily changes linked to emotions.",
    ),
    Ability(
        code="BOUNDARY_AWARENESS",
        name="Boundary Awareness",
        competency_code="SELF_MANAGEMENT",
        description="Setting and respecting personal boundaries, expressing genuine needs, and speaking up without fearing displeasing others.",
    ),
    Ability(
        code="SELF_CONFIDENCE",
        name="Self-Confidence",
        competency_code="SELF_MANAGEMENT",
        description="Accepting yourself as you are, believing in your strengths, and receiving constructive feedback without defensiveness.",
    ),
    Ability(
        code="SELF_ACTUALIZATION",
        name="Self-Actualization",
        competency_code="SELF_MANAGEMENT",
        description="Pursuing continuous personal growth, learning, and working toward meaningful, specific life goals.",
    ),
    Ability(
        code="INDEPENDENCE",
        name="Independence",
        competency_code="SELF_MANAGEMENT",
        description="Directing your own choices autonomously at work and home without excessive reliance on external validation.",
    ),
    # INTERPERSONAL_MANAGEMENT (5 abilities)
    Ability(
        code="EMPATHY",
        name="Empathy",
        competency_code="INTERPERSONAL_MANAGEMENT",
        description="Sensing, understanding, and validating the feelings and perspectives of other people.",
    ),
    Ability(
        code="VERBAL_EXPRESSION",
        name="Verbal Expression",
        competency_code="INTERPERSONAL_MANAGEMENT",
        description="Expressing thoughts, emotions, and intentions clearly, accurately, and constructively in speech.",
    ),
    Ability(
        code="NON_VERBAL_COMMUNICATION",
        name="Non-verbal Communication",
        competency_code="INTERPERSONAL_MANAGEMENT",
        description="Accurately interpreting and communicating via facial expressions, body language, tone, and physical cues.",
    ),
    Ability(
        code="ASSERTIVENESS",
        name="Assertiveness",
        competency_code="INTERPERSONAL_MANAGEMENT",
        description="Expressing your beliefs and defending boundaries respectfully, firmly, and directly without aggression.",
    ),
    Ability(
        code="CONFLICT_MANAGEMENT",
        name="Conflict Management",
        competency_code="INTERPERSONAL_MANAGEMENT",
        description="De-escalating disagreements, exploring differences constructively, and creating collaborative resolutions.",
    ),
    # STRESS_MANAGEMENT (5 abilities)
    Ability(
        code="STRESS_TOLERANCE",
        name="Stress Tolerance",
        competency_code="STRESS_MANAGEMENT",
        description="Maintaining equilibrium and effectiveness when facing demanding pressures, adversity, or unexpected hurdles.",
    ),
    Ability(
        code="COGNITIVE_FLEXIBILITY",
        name="Cognitive Flexibility",
        competency_code="STRESS_MANAGEMENT",
        description="Adapting ideas, perspectives, and strategies fluidly in response to changing conditions.",
    ),
    Ability(
        code="EMOTIONAL_REGULATION",
        name="Emotional Regulation",
        competency_code="STRESS_MANAGEMENT",
        description="Managing emotional reactivity, centering yourself under stress, and regaining composure swiftly.",
    ),
    Ability(
        code="OPTIMISM",
        name="Optimism",
        competency_code="STRESS_MANAGEMENT",
        description="Maintaining a constructive outlook, persevering through obstacles, and anticipating positive resolutions.",
    ),
    Ability(
        code="SOCIAL_RESOURCES",
        name="Social Resources",
        competency_code="STRESS_MANAGEMENT",
        description="Cultivating and drawing upon trusted external support networks, colleagues, and friendships during distress.",
    ),
    # SPIRIT_MANAGEMENT (5 abilities)
    Ability(
        code="BELIEF_INFLUENCE",
        name="Belief Influence",
        competency_code="SPIRIT_MANAGEMENT",
        description="Aligning daily behaviors and choices with your deeply held personal convictions and ethical principles.",
    ),
    Ability(
        code="CLARITY",
        name="Clarity",
        competency_code="SPIRIT_MANAGEMENT",
        description="Cultivating mental lucidity, tranquil stillness, and clear focus amid external noise and distraction.",
    ),
    Ability(
        code="ENERGY_AWARENESS",
        name="Energy Awareness",
        competency_code="SPIRIT_MANAGEMENT",
        description="Sensing, replenishing, and stewarding physical, emotional, and mental energy levels throughout the day.",
    ),
    Ability(
        code="COMMUNITY_BUILDING",
        name="Community Building",
        competency_code="SPIRIT_MANAGEMENT",
        description="Building inclusive connections, mutual goodwill, and a deep sense of belonging within groups.",
    ),
    Ability(
        code="MEANING_MAKING",
        name="Meaning Making",
        competency_code="SPIRIT_MANAGEMENT",
        description="Extracting personal growth, purpose, and deeper significance from everyday life experiences.",
    ),
    # EXECUTIVE_FUNCTION (5 abilities)
    Ability(
        code="PLANNING",
        name="Planning",
        competency_code="EXECUTIVE_FUNCTION",
        description="Formulating coherent step-by-step strategies, anticipatory schedules, and structures to achieve objectives.",
    ),
    Ability(
        code="PRIORITIZING",
        name="Prioritizing",
        competency_code="EXECUTIVE_FUNCTION",
        description="Discerning high-impact actions from distractions to channel attention and resources effectively.",
    ),
    Ability(
        code="MOTIVATION",
        name="Motivation",
        competency_code="EXECUTIVE_FUNCTION",
        description="Igniting and sustaining intrinsic momentum, enthusiasm, and persistence across short and long tasks.",
    ),
    Ability(
        code="ATTENTION_SPAN",
        name="Attention Span",
        competency_code="EXECUTIVE_FUNCTION",
        description="Sustaining concentrated focus on current priorities while actively resisting cognitive interruptions.",
    ),
    Ability(
        code="ORGANIZATION",
        name="Organization",
        competency_code="EXECUTIVE_FUNCTION",
        description="Arranging tasks, environments, schedules, and information into orderly, functional systems.",
    ),
    # DECISION_MAKING (5 abilities)
    Ability(
        code="PROCESSING_SPEED",
        name="Processing Speed",
        competency_code="DECISION_MAKING",
        description="Quickly absorbing, synthesizing, and interpreting information to make timely, well-informed choices.",
    ),
    Ability(
        code="IMPULSE_CONTROL",
        name="Impulse Control",
        competency_code="DECISION_MAKING",
        description="Resisting hasty impulses, pausing between stimulus and reaction, and considering downstream consequences.",
    ),
    Ability(
        code="REALITY_TESTING",
        name="Reality Testing",
        competency_code="DECISION_MAKING",
        description="Accurately assessing objective facts and situational realities without distorting them with subjective bias.",
    ),
    Ability(
        code="ABSTRACTION",
        name="Abstraction",
        competency_code="DECISION_MAKING",
        description="Discerning underlying patterns, synthesizing complex concepts, and applying principles across different contexts.",
    ),
    Ability(
        code="PROBLEM_SOLVING",
        name="Problem Solving",
        competency_code="DECISION_MAKING",
        description="Dismantling complex challenges methodically by combining objective analysis with intuitive emotional insight.",
    ),
)


__all__ = [
    "ABILITY_COUNT",
    "AbilityCode",
    "Ability",
    "ABILITY_RECORDS",
]
