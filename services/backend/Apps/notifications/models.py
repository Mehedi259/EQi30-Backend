from django.conf import settings
from django.db import models

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class UserReminder(models.Model):
    """Daily practice reminder settings (delivery is implemented later)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminder"
    )
    reminder_time = models.TimeField(null=True, blank=True)
    repeat_days = models.JSONField(
        default=list, blank=True, help_text='Day codes, e.g. ["MON", "WED", "FRI"].'
    )
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reminder of {self.user} ({'on' if self.is_active else 'off'})"
