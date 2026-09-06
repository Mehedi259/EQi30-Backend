import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from Apps.abilities.models import Competency


class JourneyType(models.TextChoices):
    AI_RECOMMENDED = "AI_RECOMMENDED", "AI recommended"
    CUSTOM = "CUSTOM", "Custom"


def default_session_expiry():
    return timezone.now() + timedelta(minutes=settings.ANONYMOUS_SESSION_TTL_MINUTES)


def default_total_days():
    return settings.JOURNEY_TOTAL_DAYS


class GrowthPlan(models.Model):
    """Growth pace option (Low / Medium / High)."""

    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    abilities_per_day = models.PositiveSmallIntegerField(default=1)
    estimated_minutes = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["abilities_per_day"]

    def __str__(self):
        return self.name


class PracticeTimeOption(models.Model):
    """Preferred practice window (Morning / Midday / Evening / Flexible)."""

    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_fixed = models.BooleanField(
        default=True, help_text="Flexible options have no fixed window."
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class GuidedJourneyImage(models.Model):
    """Before → After image pair shown per competency before authentication."""

    competency = models.ForeignKey(
        Competency, on_delete=models.CASCADE, related_name="journey_images"
    )
    before_image = models.ImageField(upload_to="guided_journey/")
    after_image = models.ImageField(upload_to="guided_journey/")
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"Guided journey images for {self.competency}"


class AnonymousOnboardingSession(models.Model):
    """Pre-registration onboarding container.

    Holds the AI assessment, priorities and preferences until the user
    registers. Expired sessions (and their data) are deleted — global
    catalog data is never touched by that cleanup.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLAIMED = "CLAIMED", "Claimed"
        EXPIRED = "EXPIRED", "Expired"

    session_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboarding_sessions",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    journey_type = models.CharField(
        max_length=20, choices=JourneyType.choices, default=JourneyType.AI_RECOMMENDED
    )
    growth_plan = models.ForeignKey(
        GrowthPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    practice_time = models.ForeignKey(
        PracticeTimeOption, on_delete=models.SET_NULL, null=True, blank=True
    )
    expires_at = models.DateTimeField(default=default_session_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Onboarding session {self.session_uuid} ({self.status})"

    @property
    def is_expired(self):
        return self.status == self.Status.EXPIRED or timezone.now() >= self.expires_at


class AssessmentResult(models.Model):
    """AI assessment score + priorities for one competency.

    ``ai_priority`` is the AI recommendation and is never overwritten by the
    user; a customized order is stored separately in ``user_priority``.
    """

    session = models.ForeignKey(
        AnonymousOnboardingSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assessment_results",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="assessment_results",
    )
    competency = models.ForeignKey(
        Competency, on_delete=models.CASCADE, related_name="assessment_results"
    )
    score = models.FloatField(null=True, blank=True)
    ai_priority = models.PositiveSmallIntegerField()
    user_priority = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ai_priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "competency"],
                condition=models.Q(session__isnull=False),
                name="unique_result_per_session_competency",
            ),
            models.UniqueConstraint(
                fields=["user", "competency"],
                condition=models.Q(user__isnull=False),
                name="unique_result_per_user_competency",
            ),
        ]

    def __str__(self):
        return f"{self.competency} (AI priority {self.ai_priority})"


class UserJourney(models.Model):
    """A personalized 30-day challenge instance."""

    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="journeys"
    )
    journey_type = models.CharField(
        max_length=20, choices=JourneyType.choices, default=JourneyType.AI_RECOMMENDED
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.NOT_STARTED
    )
    start_date = models.DateField(null=True, blank=True)
    current_day = models.PositiveSmallIntegerField(default=0)
    total_days = models.PositiveSmallIntegerField(default=default_total_days)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "user journeys"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=~models.Q(status="COMPLETED"),
                name="unique_active_journey_per_user",
            )
        ]

    def __str__(self):
        return f"Journey of {self.user} ({self.status}, day {self.current_day})"
