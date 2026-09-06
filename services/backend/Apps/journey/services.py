"""Business logic for onboarding, journey generation and daily scheduling.

Scheduling model
----------------
The personalized ability order is: competencies sorted by their final
priority (AI recommendation, or the user's custom order when the journey
type is CUSTOM), each contributing its 5 abilities in ``default_order``.

A journey lasts ``total_days`` (confirmed: 30). The growth pace controls
how many sessions each day holds (Low 1 / Medium 2 / High 3). Day *d*
covers the global slots ``[(d-1)*pace, d*pace)``; slot *i* maps to ability
``order[i % 30]`` with content day ``i // 30 + 1`` — so every pace covers
all 30 abilities at least once, and faster paces revisit abilities with
deeper day-2/day-3 content while still filling the full 30 days.
"""

from django.db import transaction
from django.utils import timezone

from Apps.abilities.models import Ability, Competency
from Apps.learning.models import AbilityDayContent, UserDailySession

from .models import (
    AnonymousOnboardingSession,
    AssessmentResult,
    JourneyType,
    UserJourney,
)

DEFAULT_SESSION_MINUTES = 5


# ---------------------------------------------------------------------------
# Anonymous onboarding
# ---------------------------------------------------------------------------

def purge_expired_sessions():
    """Delete anonymous data whose 10-minute window has passed.

    Cascades to the session's assessment results only — global data
    (abilities, images, learning options, …) is never touched.
    """
    return AnonymousOnboardingSession.objects.filter(
        status=AnonymousOnboardingSession.Status.ACTIVE,
        expires_at__lte=timezone.now(),
    ).delete()


def claim_onboarding_session(session_uuid, user):
    """Attach anonymous onboarding data to a freshly registered user.

    Runs inside the registration transaction. Returns True when the data
    was attached, False when the session was missing, expired or claimed
    (registration itself still succeeds in that case).
    """
    try:
        session = AnonymousOnboardingSession.objects.select_for_update().get(
            session_uuid=session_uuid
        )
    except AnonymousOnboardingSession.DoesNotExist:
        return False
    if session.status != AnonymousOnboardingSession.Status.ACTIVE or session.is_expired:
        return False

    # Move the assessment to the user (replacing any stale personal copy).
    AssessmentResult.objects.filter(user=user).delete()
    session.assessment_results.update(user=user, session=None)

    profile = user.profile
    profile.growth_plan = session.growth_plan
    profile.practice_time = session.practice_time
    profile.save(update_fields=["growth_plan", "practice_time"])

    if not user.journeys.exclude(status=UserJourney.Status.COMPLETED).exists():
        UserJourney.objects.create(user=user, journey_type=session.journey_type)

    session.user = user
    session.status = AnonymousOnboardingSession.Status.CLAIMED
    session.save(update_fields=["user", "status"])
    return True


# ---------------------------------------------------------------------------
# Personalized ordering
# ---------------------------------------------------------------------------

def get_active_journey(user):
    return (
        user.journeys.exclude(status=UserJourney.Status.COMPLETED)
        .order_by("-created_at")
        .first()
    )


def ensure_journey(user):
    journey = get_active_journey(user)
    if journey is None:
        journey = UserJourney.objects.create(user=user)
    return journey


def get_priority_map(user, journey=None):
    """competency_id -> final priority, honouring the journey type."""
    journey = journey or get_active_journey(user)
    journey_type = journey.journey_type if journey else JourneyType.AI_RECOMMENDED
    priorities = {}
    for result in AssessmentResult.objects.filter(user=user):
        if journey_type == JourneyType.CUSTOM and result.user_priority:
            priorities[result.competency_id] = result.user_priority
        else:
            priorities[result.competency_id] = result.ai_priority
    return priorities


def ordered_competencies(user, journey=None):
    """Active competencies in the user's final personalized order."""
    priorities = get_priority_map(user, journey)
    competencies = list(
        Competency.objects.filter(is_active=True).prefetch_related("abilities")
    )
    competencies.sort(key=lambda c: (priorities.get(c.id, 99), c.display_order, c.id))
    return competencies


def ordered_abilities(user, journey=None):
    """The 30 abilities flattened in personalized journey order."""
    abilities = []
    for competency in ordered_competencies(user, journey):
        abilities.extend(
            a for a in sorted(
                competency.abilities.all(), key=lambda a: (a.default_order, a.id)
            )
            if a.is_active
        )
    return abilities


def get_pace(user):
    profile = getattr(user, "profile", None)
    plan = profile.growth_plan if profile else None
    return plan.abilities_per_day if plan else 1


# ---------------------------------------------------------------------------
# Daily scheduling
# ---------------------------------------------------------------------------

def refresh_journey_day(journey):
    """Start the journey on first access and advance the day by date."""
    today = timezone.localdate()
    if journey.status == UserJourney.Status.NOT_STARTED:
        journey.status = UserJourney.Status.IN_PROGRESS
        journey.start_date = today
        journey.current_day = 1
        journey.save(update_fields=["status", "start_date", "current_day"])
    elif journey.status == UserJourney.Status.IN_PROGRESS:
        day = (today - journey.start_date).days + 1
        if day > journey.total_days:
            journey.current_day = journey.total_days
            journey.status = UserJourney.Status.COMPLETED
            journey.completed_at = timezone.now()
            journey.save(update_fields=["current_day", "status", "completed_at"])
        elif day != journey.current_day:
            journey.current_day = max(day, 1)
            journey.save(update_fields=["current_day"])
    return journey


def day_slots(journey, pace, abilities, day):
    """(ability, content_day) pairs scheduled for the given journey day."""
    if not abilities:
        return []
    slots = []
    for slot in range((day - 1) * pace, day * pace):
        ability = abilities[slot % len(abilities)]
        content_day = slot // len(abilities) + 1
        slots.append((ability, content_day))
    return slots


@transaction.atomic
def build_today_sessions(user, journey):
    """Create (idempotently) and return today's UserDailySession rows."""
    pace = get_pace(user)
    abilities = ordered_abilities(user, journey)
    sessions = []
    for ability, content_day in day_slots(journey, pace, abilities, journey.current_day):
        session, _ = UserDailySession.objects.get_or_create(
            user=user,
            journey=journey,
            ability=ability,
            day_number=journey.current_day,
            defaults={"content_day": content_day},
        )
        sessions.append(session)
    return sessions


def maybe_complete_journey(journey):
    """Mark the journey completed once the final day's sessions are done."""
    if journey is None or journey.status != UserJourney.Status.IN_PROGRESS:
        return journey
    if journey.current_day < journey.total_days:
        return journey
    final_day = journey.sessions.filter(day_number=journey.total_days)
    if final_day.exists() and not final_day.exclude(
        status=UserDailySession.Status.COMPLETED
    ).exists():
        journey.status = UserJourney.Status.COMPLETED
        journey.completed_at = timezone.now()
        journey.save(update_fields=["status", "completed_at"])
    return journey


# ---------------------------------------------------------------------------
# API payloads
# ---------------------------------------------------------------------------

def _journey_meta(journey):
    return {
        "id": journey.id,
        "journey_type": journey.journey_type,
        "status": journey.status,
        "start_date": journey.start_date,
        "current_day": journey.current_day,
        "total_days": journey.total_days,
        "completed_at": journey.completed_at,
    }


def _icon_url(obj):
    return obj.icon.url if getattr(obj, "icon", None) else None


def journey_overview(user):
    """The six competency sections in the exact personalized order."""
    journey = ensure_journey(user)
    completed_ability_ids = set(
        UserDailySession.objects.filter(
            user=user, status=UserDailySession.Status.COMPLETED
        ).values_list("ability_id", flat=True)
    )
    priorities = get_priority_map(user, journey)

    sections = []
    total = done = 0
    for index, competency in enumerate(ordered_competencies(user, journey), start=1):
        abilities = []
        for ability in sorted(
            competency.abilities.all(), key=lambda a: (a.default_order, a.id)
        ):
            if not ability.is_active:
                continue
            total += 1
            completed = ability.id in completed_ability_ids
            done += completed
            abilities.append(
                {
                    "id": ability.id,
                    "name": ability.name,
                    "description": ability.description,
                    "icon": _icon_url(ability),
                    "is_completed": completed,
                }
            )
        sections.append(
            {
                "priority": priorities.get(competency.id, index),
                "competency": {
                    "id": competency.id,
                    "name": competency.name,
                    "code": competency.code,
                    "description": competency.description,
                    "icon": _icon_url(competency),
                },
                "abilities": abilities,
            }
        )

    return {
        "journey": _journey_meta(journey),
        "overall_progress_percent": round(done / total * 100) if total else 0,
        "sections": sections,
    }


def _serialize_session(session, content_map):
    ability = session.ability
    content = content_map.get((ability.id, session.content_day))
    return {
        "session_id": session.id,
        "status": session.status,
        "day_number": session.day_number,
        "content_day": session.content_day,
        "has_content": content is not None,
        "estimated_minutes": content.estimated_minutes if content else DEFAULT_SESSION_MINUTES,
        "ability": {
            "id": ability.id,
            "name": ability.name,
            "description": ability.description,
            "icon": _icon_url(ability),
        },
        "competency": {
            "id": ability.competency.id,
            "name": ability.competency.name,
            "code": ability.competency.code,
        },
    }


def journey_today(user):
    """Payload for GET /journey/today/."""
    journey = refresh_journey_day(ensure_journey(user))
    profile = getattr(user, "profile", None)

    if journey.status == UserJourney.Status.COMPLETED:
        return {
            "journey": _journey_meta(journey),
            "sessions": [],
            "sessions_remaining": 0,
            "message": "Journey complete. Congratulations!",
        }

    sessions = build_today_sessions(user, journey)
    content_map = {
        (c.ability_id, c.day_number): c
        for c in AbilityDayContent.objects.filter(
            ability_id__in=[s.ability_id for s in sessions],
            day_number__in=[s.content_day for s in sessions],
        )
    }
    serialized = [_serialize_session(s, content_map) for s in sessions]
    remaining = sum(1 for s in sessions if s.status != UserDailySession.Status.COMPLETED)
    return {
        "journey": _journey_meta(journey),
        "growth_plan": profile.growth_plan.code if profile and profile.growth_plan else None,
        "practice_time": profile.practice_time.code if profile and profile.practice_time else None,
        "sessions": serialized,
        "sessions_remaining": remaining,
        "estimated_minutes_total": sum(s["estimated_minutes"] for s in serialized),
    }


def journey_history(user):
    """Payload for GET /journey/history/."""
    total_abilities = Ability.objects.filter(is_active=True).count()
    history = []
    for journey in user.journeys.all():
        completed_sessions = journey.sessions.filter(
            status=UserDailySession.Status.COMPLETED
        )
        completed_abilities = completed_sessions.values("ability").distinct().count()
        history.append(
            {
                **_journey_meta(journey),
                "created_at": journey.created_at,
                "completed_sessions": completed_sessions.count(),
                "completed_abilities": completed_abilities,
                "total_abilities": total_abilities,
                "progress_percent": round(completed_abilities / total_abilities * 100)
                if total_abilities
                else 0,
            }
        )
    return history
