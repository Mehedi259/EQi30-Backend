from django.conf import settings
from django.db import models

from Apps.abilities.models import Ability


class AbilityDayContent(models.Model):
    """Daily learning content for an ability (teaching → practice → plan → reflection)."""

    ability = models.ForeignKey(
        Ability, on_delete=models.CASCADE, related_name="day_contents"
    )
    day_number = models.PositiveSmallIntegerField(
        default=1, help_text="Content day within this ability (1 = first visit)."
    )
    title = models.CharField(max_length=200)
    teaching_content = models.TextField(blank=True)
    practice_content = models.TextField(blank=True)
    real_life_plan = models.TextField(blank=True)
    reflection_question = models.TextField(blank=True)
    estimated_minutes = models.PositiveSmallIntegerField(default=5)

    class Meta:
        ordering = ["ability", "day_number"]
        verbose_name_plural = "ability day contents"
        constraints = [
            models.UniqueConstraint(
                fields=["ability", "day_number"], name="unique_content_per_ability_day"
            )
        ]

    def __str__(self):
        return f"{self.ability.name} — day {self.day_number}: {self.title}"


class UserDailySession(models.Model):
    """One scheduled learning session of a user's journey day."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_sessions"
    )
    journey = models.ForeignKey(
        "journey.UserJourney",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sessions",
    )
    ability = models.ForeignKey(
        Ability, on_delete=models.CASCADE, related_name="user_sessions"
    )
    day_number = models.PositiveSmallIntegerField(help_text="Journey day (1–30).")
    content_day = models.PositiveSmallIntegerField(
        default=1, help_text="Which AbilityDayContent day this session uses."
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["day_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "journey", "ability", "day_number"],
                name="unique_session_per_journey_day_ability",
            )
        ]

    def __str__(self):
        return f"{self.user} · day {self.day_number} · {self.ability.name} ({self.status})"


class DailyReflection(models.Model):
    """Reflection answers captured when a session is completed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reflections"
    )
    session = models.OneToOneField(
        UserDailySession, on_delete=models.CASCADE, related_name="reflection"
    )
    response = models.CharField(
        max_length=255, blank=True, help_text="Selected quick-reflection option."
    )
    reflection_text = models.TextField(blank=True)
    practice_answer = models.TextField(blank=True)
    real_life_answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reflection of {self.user} for session {self.session_id}"


class WeeklyCheckIn(models.Model):
    """Weekly check-in answers for a journey week."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="weekly_checkins"
    )
    journey = models.ForeignKey(
        "journey.UserJourney",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="weekly_checkins",
    )
    week_number = models.PositiveSmallIntegerField()
    answers = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["week_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "journey", "week_number"],
                name="unique_checkin_per_journey_week",
            )
        ]

    def __str__(self):
        return f"Week {self.week_number} check-in of {self.user}"
