from django.contrib import admin

from .models import SupportAttachment, SupportRequest


class SupportAttachmentInline(admin.TabularInline):
    model = SupportAttachment
    extra = 0


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ["subject", "email", "user", "status", "created_at"]
    list_filter = ["status"]
    list_editable = ["status"]
    search_fields = ["subject", "email", "message"]
    inlines = [SupportAttachmentInline]
