from rest_framework import serializers

from .models import WEEKDAYS, UserReminder


class UserReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserReminder
        fields = ["reminder_time", "repeat_days", "is_active", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_repeat_days(self, value):
        invalid = [d for d in value if d not in WEEKDAYS]
        if invalid:
            raise serializers.ValidationError(
                f"Invalid day codes {invalid}; use {WEEKDAYS}."
            )
        return list(dict.fromkeys(value))  # dedupe, keep order

    def validate(self, attrs):
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", False))
        time = attrs.get("reminder_time", getattr(self.instance, "reminder_time", None))
        if is_active and time is None:
            raise serializers.ValidationError(
                {"reminder_time": "A reminder time is required to enable reminders."}
            )
        return attrs
