from django.contrib import admin

from .models import (
    AnonymousOnboardingSession,
    AssessmentResult,
    GrowthPlan,
    GuidedJourneyImage,
    PracticeTimeOption,
    UserJourney,
)


@admin.register(GrowthPlan)
class GrowthPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "abilities_per_day", "estimated_minutes", "is_active"]
    list_editable = ["is_active"]


@admin.register(PracticeTimeOption)
class PracticeTimeOptionAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "start_time", "end_time", "is_fixed"]


@admin.register(GuidedJourneyImage)
class GuidedJourneyImageAdmin(admin.ModelAdmin):
    list_display = ["competency", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_filter = ["is_active"]


class AssessmentResultInline(admin.TabularInline):
    model = AssessmentResult
    extra = 0
    readonly_fields = ["competency", "score", "ai_priority", "user_priority"]
    can_delete = False


@admin.register(AnonymousOnboardingSession)
class AnonymousOnboardingSessionAdmin(admin.ModelAdmin):
    list_display = ["session_uuid", "status", "user", "expires_at", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["session_uuid", "created_at"]
    inlines = [AssessmentResultInline]


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ["competency", "user", "session", "score", "ai_priority", "user_priority"]
    list_filter = ["competency"]


@admin.register(UserJourney)
class UserJourneyAdmin(admin.ModelAdmin):
    list_display = ["user", "journey_type", "status", "start_date", "current_day", "total_days"]
    list_filter = ["status", "journey_type"]
