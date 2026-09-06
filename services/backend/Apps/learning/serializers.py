from rest_framework import serializers

from .models import AbilityDayContent, DailyReflection, UserDailySession, WeeklyCheckIn


class AbilityDayContentSerializer(serializers.ModelSerializer):
    ability_id = serializers.IntegerField(source="ability.id", read_only=True)
    ability_name = serializers.CharField(source="ability.name", read_only=True)
    competency = serializers.CharField(source="ability.competency.name", read_only=True)

    class Meta:
        model = AbilityDayContent
        fields = [
            "id",
            "ability_id",
            "ability_name",
            "competency",
            "day_number",
            "title",
            "teaching_content",
            "practice_content",
            "real_life_plan",
            "reflection_question",
            "estimated_minutes",
        ]


class UserDailySessionSerializer(serializers.ModelSerializer):
    ability_name = serializers.CharField(source="ability.name", read_only=True)
    competency = serializers.CharField(source="ability.competency.name", read_only=True)

    class Meta:
        model = UserDailySession
        fields = [
            "id",
            "ability",
            "ability_name",
            "competency",
            "day_number",
            "content_day",
            "status",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields


class DailyReflectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReflection
        fields = [
            "id",
            "session",
            "response",
            "reflection_text",
            "practice_answer",
            "real_life_answer",
            "created_at",
        ]
        read_only_fields = ["id", "session", "created_at"]


class WeeklyCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyCheckIn
        fields = ["id", "week_number", "answers", "completed_at"]
        read_only_fields = ["id", "completed_at"]
