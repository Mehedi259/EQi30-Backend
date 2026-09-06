from django.contrib.auth import get_user_model
from rest_framework import serializers

from Apps.journey.models import GrowthPlan, PracticeTimeOption

from .models import UserProfile

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", required=False)
    growth_plan = serializers.SlugRelatedField(
        slug_field="code",
        queryset=GrowthPlan.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    practice_time = serializers.SlugRelatedField(
        slug_field="code",
        queryset=PracticeTimeOption.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = UserProfile
        fields = [
            "email",
            "full_name",
            "phone",
            "profile_image",
            "daily_goal_minutes",
            "growth_plan",
            "practice_time",
        ]

    def validate_email(self, value):
        user = self.instance.user if self.instance else None
        qs = User.objects.filter(email__iexact=value)
        if user:
            qs = qs.exclude(pk=user.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        new_email = user_data.get("email")
        if new_email and new_email != instance.user.email:
            instance.user.email = new_email
            instance.user.save(update_fields=["email"])
        return super().update(instance, validated_data)
