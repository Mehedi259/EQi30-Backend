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


def get_streak_details(user):
    """Return both consecutive streak and Doc 2's 5-of-7 'Most Days' model."""
    today = timezone.localdate()
    dates = {
        timezone.localtime(dt).date()
        for dt in _completed_sessions(user)
        .exclude(completed_at=None)
        .values_list("completed_at", flat=True)
    }
    window_start = today - timedelta(days=6)
    active_days_last_7 = sum(1 for d in dates if window_start <= d <= today)
    streak_safe = (
        active_days_last_7 >= 5
        or today in dates
        or (today - timedelta(days=1)) in dates
        or (today - timedelta(days=2)) in dates
    )
    return {
        "model": "5_of_7",
        "consecutive_days": get_streak(user),
        "active_days_last_7": active_days_last_7,
        "target_days_per_week": 5,
        "streak_safe": streak_safe,
    }


def get_pending_reflections_today(user):
    """Completed sessions from today that still lack a written DailyReflection."""
    today = timezone.localdate()
    today_sessions = [
        s
        for s in _completed_sessions(user)
        .exclude(completed_at=None)
        .select_related("ability", "ability__competency", "reflection")
        .order_by("-completed_at")
        if timezone.localtime(s.completed_at).date() == today
    ]
    if not today_sessions:
        return []

    content_map = {
        (c.ability_id, c.day_number): c
        for c in AbilityDayContent.objects.filter(
            ability_id__in=[s.ability_id for s in today_sessions],
            day_number__in=[s.content_day for s in today_sessions],
        )
    }
    pending = []
    for s in today_sessions:
        ref = getattr(s, "reflection", None)
        ref_text = (ref.reflection_text or "").strip() if ref else ""
        if ref_text:
            continue
        content = content_map.get((s.ability_id, s.content_day))
        pending.append(
            {
                "session_id": s.id,
                "ability_id": s.ability_id,
                "ability_name": s.ability.name,
                "competency_name": s.ability.competency.name,
                "reflection_question": (
                    content.reflection_question
                    if content and content.reflection_question
                    else f"What did you notice today while practicing {s.ability.name}?"
                ),
                "existing_response": ref.response if ref else "",
                "existing_practice_answer": ref.practice_answer if ref else "",
            }
        )
    return pending


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
