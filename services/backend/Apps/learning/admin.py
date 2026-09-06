from django.contrib import admin

from .models import AbilityDayContent, DailyReflection, UserDailySession, WeeklyCheckIn


@admin.register(AbilityDayContent)
class AbilityDayContentAdmin(admin.ModelAdmin):
    list_display = ["ability", "day_number", "title", "estimated_minutes"]
    list_filter = ["ability__competency", "day_number"]
    search_fields = ["title", "ability__name"]


@admin.register(UserDailySession)
class UserDailySessionAdmin(admin.ModelAdmin):
    list_display = ["user", "ability", "day_number", "content_day", "status", "completed_at"]
    list_filter = ["status", "day_number"]
    search_fields = ["user__email", "ability__name"]


@admin.register(DailyReflection)
class DailyReflectionAdmin(admin.ModelAdmin):
    list_display = ["user", "session", "created_at"]
    search_fields = ["user__email"]


@admin.register(WeeklyCheckIn)
class WeeklyCheckInAdmin(admin.ModelAdmin):
    list_display = ["user", "journey", "week_number", "completed_at"]
