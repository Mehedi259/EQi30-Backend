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
    list_display = ["name", "competency", "default_order", "is_active"]
    list_filter = ["competency", "is_active"]
    list_editable = ["default_order", "is_active"]
    search_fields = ["name"]
