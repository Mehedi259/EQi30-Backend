from django.contrib import admin

from .models import FAQ


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    search_fields = ["question", "answer"]
