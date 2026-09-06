"""Progress, streak and badge calculations — always derived from real
completion records (UserDailySession), never from cached counters."""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from Apps.abilities.models import Ability, Competency
from Apps.learning.models import AbilityDayContent, UserDailySession

from .models import Badge, UserBadge


def _completed_sessions(user):
    return UserDailySession.objects.filter(
        user=user, status=UserDailySession.Status.COMPLETED
    )


def get_streak(user):
    """Consecutive days with at least one completed session.

    A day without completions only breaks the streak once it is over —
    today still counts as "pending" until the user completes something.
    """
    dates = {
        timezone.localtime(dt).date()
        for dt in _completed_sessions(user)
        .exclude(completed_at=None)
        .values_list("completed_at", flat=True)
    }
    day = timezone.localdate()
    if day not in dates:
        day -= timedelta(days=1)
    streak = 0
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def overall_progress(user):
    total = Ability.objects.filter(is_active=True).count()
    done = _completed_sessions(user).values("ability").distinct().count()
    return {
        "completed_abilities": done,
        "total_abilities": total,
        "percent": round(done / total * 100) if total else 0,
    }


def competency_progress(user, ordered=None):
    """Per-competency ability completion, in the personalized order when given."""
    done_map = dict(
        _completed_sessions(user)
        .values_list("ability__competency")
        .annotate(done=Count("ability", distinct=True))
    )
    rows = []
    competencies = ordered or Competency.objects.filter(is_active=True).prefetch_related(
        "abilities"
    )
    for competency in competencies:
        total = sum(1 for a in competency.abilities.all() if a.is_active)
        done = done_map.get(competency.id, 0)
        rows.append(
            {
                "competency": {
                    "id": competency.id,
                    "name": competency.name,
                    "code": competency.code,
                },
                "completed_abilities": done,
                "total_abilities": total,
                "percent": round(done / total * 100) if total else 0,
            }
        )
    return rows


def weekly_activity(user):
    """Completed session counts for the last 7 days (oldest first)."""
    today = timezone.localdate()
    counts = {}
    for dt in _completed_sessions(user).exclude(completed_at=None).values_list(
        "completed_at", flat=True
    ):
        day = timezone.localtime(dt).date()
        if day > today - timedelta(days=7):
            counts[day] = counts.get(day, 0) + 1
    return [
        {"date": day, "completed": counts.get(day, 0)}
        for day in (today - timedelta(days=offset) for offset in range(6, -1, -1))
    ]


def minutes_completed_today(user):
    today = timezone.localdate()
    sessions = [
        s
        for s in _completed_sessions(user).exclude(completed_at=None).select_related()
        if timezone.localtime(s.completed_at).date() == today
    ]
    if not sessions:
        return 0
    content_minutes = {
        (c.ability_id, c.day_number): c.estimated_minutes
        for c in AbilityDayContent.objects.filter(
            ability_id__in=[s.ability_id for s in sessions]
        )
    }
    return sum(
        content_minutes.get((s.ability_id, s.content_day), 5) for s in sessions
    )


def _badge_stats(user):
    from Apps.journey.models import UserJourney

    return {
        "sessions": _completed_sessions(user).count(),
        "streak": get_streak(user),
        "abilities": _completed_sessions(user).values("ability").distinct().count(),
        "journeys": user.journeys.filter(status=UserJourney.Status.COMPLETED).count(),
    }


def evaluate_badges(user):
    """Award any newly earned badges; returns the list of new Badge objects."""
    earned_ids = set(user.badges.values_list("badge_id", flat=True))
    candidates = Badge.objects.filter(is_active=True).exclude(id__in=earned_ids)
    if not candidates:
        return []

    stats = _badge_stats(user)
    thresholds = {
        Badge.ConditionType.FIRST_SESSION: stats["sessions"],
        Badge.ConditionType.STREAK_DAYS: stats["streak"],
        Badge.ConditionType.ABILITIES_COMPLETED: stats["abilities"],
        Badge.ConditionType.JOURNEY_COMPLETED: stats["journeys"],
    }
    newly = []
    for badge in candidates:
        if thresholds.get(badge.condition_type, 0) >= max(badge.condition_value, 1):
            UserBadge.objects.get_or_create(user=user, badge=badge)
            newly.append(badge)
    return newly
