from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name", "phone", "growth_plan", "practice_time"]
    search_fields = ["user__email", "full_name"]
