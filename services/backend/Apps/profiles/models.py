from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Profile + onboarding preferences attached to every user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True)
    daily_goal_minutes = models.PositiveSmallIntegerField(default=5)

    # Preferences chosen during (anonymous) onboarding, attached on registration.
    growth_plan = models.ForeignKey(
        "journey.GrowthPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
    )
    practice_time = models.ForeignKey(
        "journey.PracticeTimeOption",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user}"
