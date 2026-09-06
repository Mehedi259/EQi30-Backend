from django.contrib import admin

from .models import UserReminder


@admin.register(UserReminder)
class UserReminderAdmin(admin.ModelAdmin):
    list_display = ["user", "reminder_time", "repeat_days", "is_active"]
    search_fields = ["user__email"]
