from rest_framework import serializers

from .models import Ability, Competency


class AbilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Ability
        fields = [
            "id", "name", "description", "icon", "default_order",
            "what_it_is", "why_it_matters", "what_you_will_do", "what_you_will_learn",
        ]


class AbilityJourneyIntroSerializer(serializers.ModelSerializer):
    ability_id = serializers.IntegerField(source="id", read_only=True)
    ability_name = serializers.CharField(source="name", read_only=True)
    competency_id = serializers.IntegerField(source="competency.id", read_only=True)
    competency_name = serializers.CharField(source="competency.name", read_only=True)
    competency_code = serializers.CharField(source="competency.code", read_only=True)
    abilities = serializers.SerializerMethodField()
    what_it_is = serializers.SerializerMethodField()
    why_it_matters = serializers.SerializerMethodField()
    what_you_will_do = serializers.SerializerMethodField()
    what_you_will_learn = serializers.SerializerMethodField()
    total_days = serializers.SerializerMethodField()
    total_microskills = serializers.SerializerMethodField()

    class Meta:
        model = Ability
        fields = [
            "id", "ability_id", "name", "ability_name",
            "description", "icon", "default_order",
            "competency_id", "competency_name", "competency_code",
            "what_it_is", "why_it_matters", "what_you_will_do", "what_you_will_learn",
            "total_days", "total_microskills", "abilities",
        ]

    def get_what_it_is(self, obj):
        return obj.what_it_is or obj.competency.what_it_is or obj.description

    def get_why_it_matters(self, obj):
        return obj.why_it_matters or obj.competency.why_it_matters

    def get_what_you_will_do(self, obj):
        return obj.what_you_will_do or obj.competency.what_you_will_do

    def get_what_you_will_learn(self, obj):
        return obj.what_you_will_learn or obj.competency.what_you_will_learn or []

    def get_total_days(self, obj):
        return 30

    def get_total_microskills(self, obj):
        count = obj.day_contents.count()
        return count if count > 0 else 60

    def get_abilities(self, obj):
        qs = obj.competency.abilities.filter(is_active=True)
        return AbilitySerializer(qs, many=True, context=self.context).data


class CompetencySerializer(serializers.ModelSerializer):
    abilities = serializers.SerializerMethodField()

    class Meta:
        model = Competency
        fields = [
            "id", "name", "code", "description", "icon", 
            "what_it_is", "why_it_matters", "what_you_will_do", "what_you_will_learn",
            "display_order", "abilities"
        ]

    def get_abilities(self, obj):
        qs = obj.abilities.filter(is_active=True)
        return AbilitySerializer(qs, many=True, context=self.context).data


class CompetencySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Competency
        fields = ["id", "name", "code", "icon"]
