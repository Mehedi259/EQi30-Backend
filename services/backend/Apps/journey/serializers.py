from rest_framework import serializers

from Apps.abilities.models import Competency
from Apps.abilities.serializers import CompetencySummarySerializer

from .models import (
    AnonymousOnboardingSession,
    AssessmentResult,
    GrowthPlan,
    GuidedJourneyImage,
    JourneyType,
    PracticeTimeOption,
)


def active_competencies():
    return Competency.objects.filter(is_active=True)


class AssessmentResultSerializer(serializers.ModelSerializer):
    competency = serializers.SlugRelatedField(slug_field="code", read_only=True)
    competency_name = serializers.CharField(source="competency.name", read_only=True)

    class Meta:
        model = AssessmentResult
        fields = ["competency", "competency_name", "score", "ai_priority", "user_priority"]


class SessionStateSerializer(serializers.ModelSerializer):
    growth_plan = serializers.SlugRelatedField(slug_field="code", read_only=True)
    practice_time = serializers.SlugRelatedField(slug_field="code", read_only=True)
    results = AssessmentResultSerializer(
        source="assessment_results", many=True, read_only=True
    )

    class Meta:
        model = AnonymousOnboardingSession
        fields = [
            "session_uuid",
            "status",
            "journey_type",
            "growth_plan",
            "practice_time",
            "expires_at",
            "results",
        ]


class AssessmentEntrySerializer(serializers.Serializer):
    competency = serializers.SlugRelatedField(
        slug_field="code", queryset=active_competencies()
    )
    score = serializers.FloatField(min_value=0, max_value=100)
    ai_priority = serializers.IntegerField(min_value=1)


def _validate_full_coverage(entries, priority_key):
    """All active competencies exactly once, priorities 1..N without duplicates."""
    active_ids = set(active_competencies().values_list("id", flat=True))
    competency_ids = [entry["competency"].id for entry in entries]
    priorities = [entry[priority_key] for entry in entries]

    if len(competency_ids) != len(set(competency_ids)):
        raise serializers.ValidationError("Each competency may appear only once.")
    if set(competency_ids) != active_ids:
        raise serializers.ValidationError(
            f"Results must cover all {len(active_ids)} competencies."
        )
    if len(priorities) != len(set(priorities)):
        raise serializers.ValidationError("Duplicate priorities are not allowed.")
    if set(priorities) != set(range(1, len(active_ids) + 1)):
        raise serializers.ValidationError(
            f"Priorities must use each value 1–{len(active_ids)} exactly once."
        )
    return entries


class AssessmentSubmitSerializer(serializers.Serializer):
    results = AssessmentEntrySerializer(many=True)

    def validate_results(self, value):
        return _validate_full_coverage(value, "ai_priority")


class PriorityEntrySerializer(serializers.Serializer):
    competency = serializers.SlugRelatedField(
        slug_field="code", queryset=active_competencies()
    )
    priority = serializers.IntegerField(min_value=1)


class PrioritiesUpdateSerializer(serializers.Serializer):
    journey_type = serializers.ChoiceField(choices=JourneyType.choices)
    priorities = PriorityEntrySerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs["journey_type"] == JourneyType.CUSTOM:
            if not attrs.get("priorities"):
                raise serializers.ValidationError(
                    {"priorities": "A custom journey requires the full priority list."}
                )
            _validate_full_coverage(attrs["priorities"], "priority")
        return attrs


class GrowthPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrowthPlan
        fields = ["code", "name", "abilities_per_day", "estimated_minutes"]


class PracticeTimeOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeTimeOption
        fields = ["code", "name", "start_time", "end_time", "is_fixed"]


class GrowthPlanSelectSerializer(serializers.Serializer):
    growth_plan = serializers.SlugRelatedField(
        slug_field="code", queryset=GrowthPlan.objects.filter(is_active=True)
    )


class PracticeTimeSelectSerializer(serializers.Serializer):
    practice_time = serializers.SlugRelatedField(
        slug_field="code", queryset=PracticeTimeOption.objects.all()
    )


class GuidedJourneyImageSerializer(serializers.ModelSerializer):
    competency = CompetencySummarySerializer(read_only=True)

    class Meta:
        model = GuidedJourneyImage
        fields = ["id", "competency", "before_image", "after_image", "display_order"]
