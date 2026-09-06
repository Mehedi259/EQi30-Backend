from rest_framework import serializers

from .models import Ability, Competency


class AbilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Ability
        fields = ["id", "name", "description", "icon", "default_order"]


class CompetencySerializer(serializers.ModelSerializer):
    abilities = serializers.SerializerMethodField()

    class Meta:
        model = Competency
        fields = ["id", "name", "code", "description", "icon", "display_order", "abilities"]

    def get_abilities(self, obj):
        qs = obj.abilities.filter(is_active=True)
        return AbilitySerializer(qs, many=True, context=self.context).data


class CompetencySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Competency
        fields = ["id", "name", "code", "icon"]
