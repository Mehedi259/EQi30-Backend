"""Django-grounded context enrichment and EQ improvement suggestions for AI endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from django.utils import timezone
from rest_framework.permissions import BasePermission

from Apps.journey import services as journey_services
from Apps.journey.models import AnonymousOnboardingSession, AssessmentResult
from Apps.learning.models import DailyReflection, WeeklyCheckIn
from Apps.progress import services as progress_services


def _extract_valid_uuid(raw_value: Any) -> Optional[uuid.UUID]:
    if not raw_value or not isinstance(raw_value, str):
        return None
    candidate = raw_value.strip()
    if candidate.startswith("onboarding-"):
        candidate = candidate[len("onboarding-") :]
    try:
        return uuid.UUID(candidate)
    except ValueError:
        return None


class IsAuthenticatedOrActiveOnboardingSession(BasePermission):
    """Allow authenticated JWT callers or active non-expired onboarding sessions."""

    message = "Authentication or an active onboarding session UUID is required."

    def has_permission(self, request, view) -> bool:
        if request.user and request.user.is_authenticated:
            return True

        data = request.data if isinstance(request.data, dict) else {}
        candidates = (
            request.headers.get("X-Onboarding-Session"),
            request.query_params.get("session_uuid"),
            data.get("session_uuid"),
            data.get("user_ref"),
        )
        for raw in candidates:
            parsed = _extract_valid_uuid(raw)
            if parsed is None:
                continue
            if AnonymousOnboardingSession.objects.filter(
                session_uuid=parsed,
                status=AnonymousOnboardingSession.Status.ACTIVE,
                expires_at__gt=timezone.now(),
            ).exists():
                return True
        return False


def build_user_ai_context(user, supplied_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble grounded journey, assessment, reflection, and progress blocks from DB."""
    supplied = supplied_context if isinstance(supplied_context, dict) else {}
    journey = journey_services.get_active_journey(user)
    ordered_abs = journey_services.ordered_abilities(user, journey)
    ordered_comps = journey_services.ordered_competencies(user, journey)

    results = list(
        AssessmentResult.objects.filter(user=user).select_related("competency").order_by("ai_priority")
    )
    recent_reflections = list(
        DailyReflection.objects.filter(user=user)
        .select_related("session__ability", "session__ability__competency")
        .order_by("-created_at")[:5]
    )
    latest_checkin = WeeklyCheckIn.objects.filter(user=user).order_by("-week_number").first()

    journey_block = {
        "journey_type": journey.journey_type if journey else None,
        "status": journey.status if journey else None,
        "current_day": journey.current_day if journey else None,
        "total_days": journey.total_days if journey else 30,
        "active_abilities": [a.name for a in ordered_abs[:3]],
        "pace_per_day": journey_services.get_pace(user),
    }
    comp_block = {
        "top_priorities": [c.name for c in ordered_comps[:2]],
        "scores": [
            {"competency": r.competency.name, "score": r.score, "ai_priority": r.ai_priority}
            for r in results
        ],
    }
    first_ability = ordered_abs[0] if ordered_abs else None
    ability_block = (
        {
            "name": first_ability.name,
            "competency": first_ability.competency.name,
            "what_it_is": first_ability.what_it_is or first_ability.description,
        }
        if first_ability
        else {}
    )
    progress_block = {
        "overall": progress_services.overall_progress(user),
        "streak": progress_services.get_streak_details(user),
        "recent_reflections": [
            {
                "ability": r.session.ability.name,
                "feeling": r.response,
                "practice_note": r.practice_answer[:200],
                "reflection": r.reflection_text[:250],
            }
            for r in recent_reflections
        ],
        "latest_weekly_checkin": (
            {"week": latest_checkin.week_number, "answers": latest_checkin.answers}
            if latest_checkin
            else None
        ),
    }

    return {
        "journey": supplied.get("journey") or journey_block,
        "competency": supplied.get("competency") or comp_block,
        "ability": supplied.get("ability") or ability_block,
        "progress": supplied.get("progress") or progress_block,
    }


def build_grounded_suggestions(user) -> Dict[str, Any]:
    """Generate personalized EQ improvement suggestions grounded in saved reflections & scores."""
    context = build_user_ai_context(user)
    journey_block = context["journey"]
    comp_block = context["competency"]
    progress_block = context["progress"]
    reflections: List[Dict[str, Any]] = progress_block.get("recent_reflections", [])
    scores: List[Dict[str, Any]] = comp_block.get("scores", [])

    ordered_abs = journey_services.ordered_abilities(user)
    focus_ability = ordered_abs[0] if ordered_abs else None
    second_ability = ordered_abs[1] if len(ordered_abs) > 1 else None

    lowest_comp = scores[0]["competency"] if scores else (
        focus_ability.competency.name if focus_ability else "Self-Management"
    )
    latest_feeling = next((r["feeling"] for r in reflections if r.get("feeling")), "")

    suggestions: List[Dict[str, str]] = []
    if focus_ability:
        suggestions.append(
            {
                "title": f"Deepen {focus_ability.name}",
                "detail": (
                    f"Focus your 5-minute rep on {focus_ability.name} "
                    f"({focus_ability.what_you_will_do or focus_ability.description or 'today’s prompt'})."
                ),
                "action": "start_practice",
                "ability_id": str(focus_ability.id),
                "ability_name": focus_ability.name,
            }
        )

    if reflections:
        latest_ab = reflections[0].get("ability") or "your last exercise"
        feeling_clause = f" when feeling {latest_feeling}" if latest_feeling else ""
        suggestions.append(
            {
                "title": f"Build on your {latest_ab} reflection",
                "detail": (
                    f"You logged {len(reflections)} recent reflection(s){feeling_clause}. "
                    f"Notice the moment before reacting today and apply one small If-Then pause."
                ),
                "action": "open_chat",
                "ability_id": str(focus_ability.id) if focus_ability else "",
                "ability_name": latest_ab,
            }
        )
    else:
        suggestions.append(
            {
                "title": "Log today's feeling & reflection",
                "detail": (
                    f"Complete your reflection after practicing {focus_ability.name if focus_ability else lowest_comp} "
                    "so your AI suggestions adapt to your real triggers and patterns."
                ),
                "action": "start_practice",
                "ability_id": str(focus_ability.id) if focus_ability else "",
                "ability_name": focus_ability.name if focus_ability else lowest_comp,
            }
        )

    if second_ability:
        suggestions.append(
            {
                "title": f"Pair with {second_ability.name}",
                "detail": (
                    f"Your top growth priority in {lowest_comp} pairs well with {second_ability.name} "
                    "when switching between tasks or conversations."
                ),
                "action": "reorder_abilities",
                "ability_id": str(second_ability.id),
                "ability_name": second_ability.name,
            }
        )

    summary = (
        f"You're on Day {journey_block.get('current_day') or 1} focusing on "
        f"{', '.join(journey_block.get('active_abilities') or [lowest_comp])}."
    )
    if latest_feeling:
        summary += f" Recent feeling logged: {latest_feeling}."

    return {
        "summary": summary,
        "lowest_competency": lowest_comp,
        "recommended_ability": (
            {"id": focus_ability.id, "name": focus_ability.name}
            if focus_ability
            else None
        ),
        "grounded_reflections_count": len(reflections),
        "suggestions": suggestions,
    }

