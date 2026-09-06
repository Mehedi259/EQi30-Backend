from django.conf import settings
from django.db import models


class Badge(models.Model):
    """Earnable badge; the rule is expressed as condition_type + condition_value."""

    class ConditionType(models.TextChoices):
        FIRST_SESSION = "FIRST_SESSION", "Completed first session"
        STREAK_DAYS = "STREAK_DAYS", "Reached a daily streak"
        ABILITIES_COMPLETED = "ABILITIES_COMPLETED", "Completed N abilities"
        JOURNEY_COMPLETED = "JOURNEY_COMPLETED", "Completed N journeys"

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to="badges/", null=True, blank=True)
    condition_type = models.CharField(max_length=30, choices=ConditionType.choices)
    condition_value = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges"
    )
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-earned_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "badge"], name="unique_badge_per_user")
        ]

    def __str__(self):
        return f"{self.badge} → {self.user}"
