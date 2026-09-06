from django.contrib import admin

from .models import Resource, ResourceFavorite


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "competency", "is_active", "created_at"]
    list_filter = ["type", "competency", "is_active"]
    search_fields = ["title", "description"]


@admin.register(ResourceFavorite)
class ResourceFavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "resource", "created_at"]
