from django.contrib import admin

from .models import LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ["type", "title", "version", "is_active", "published_at"]
    list_filter = ["type", "is_active"]
