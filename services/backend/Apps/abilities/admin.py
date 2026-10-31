from django.contrib import admin

from .models import Ability, Competency


class AbilityInline(admin.TabularInline):
    model = Ability
    extra = 0
    fields = ["name", "default_order", "is_active", "description", "icon"]


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    prepopulated_fields = {"code": ["name"]}
    inlines = [AbilityInline]


@admin.register(Ability)
class AbilityAdmin(admin.ModelAdmin):
    list_display = ["name", "competency", "default_order", "has_journey_intro", "is_active"]
    list_filter = ["competency", "is_active"]
    list_editable = ["default_order", "is_active"]
    search_fields = ["name", "competency__name"]
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "competency", "default_order", "is_active", "description", "icon"),
        }),
        ("30 Microskill Journey Introduction", {
            "fields": ("what_it_is", "why_it_matters", "what_you_will_do", "what_you_will_learn"),
            "description": "Configure the 30-day microskill journey introduction shown on the Start Journey screen for this ability.",
        }),
    )

    @admin.display(boolean=True, description="Journey Intro Configured")
    def has_journey_intro(self, obj):
        return bool(obj.what_it_is or obj.why_it_matters)
