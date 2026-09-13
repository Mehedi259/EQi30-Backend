from django.conf import settings
from django.db import models

from Apps.abilities.models import Competency


class Resource(models.Model):
    """Learning resource (video / audio / article), filterable by competency."""

    class ResourceType(models.TextChoices):
        VIDEO = "VIDEO", "Video"
        AUDIO = "AUDIO", "Audio"
        ARTICLE = "ARTICLE", "Article"

    class ResourceCategory(models.TextChoices):
        MEDITATION = "MEDITATION", "Meditation"
        YOGA = "YOGA", "Yoga"
        ARTICLE = "ARTICLE", "Article"
        JOURNEY = "JOURNEY", "Journey"

    class DifficultyLevel(models.TextChoices):
        BEGINNER = "BEGINNER", "Beginner"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        ADVANCED = "ADVANCED", "Advanced"

    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=10, choices=ResourceType.choices)
    category = models.CharField(max_length=20, choices=ResourceCategory.choices, default=ResourceCategory.MEDITATION)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    difficulty_level = models.CharField(max_length=20, choices=DifficultyLevel.choices, null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    competency = models.ForeignKey(
        Competency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
    )
    file = models.FileField(upload_to="resources/", null=True, blank=True)
    url = models.URLField(blank=True)
    thumbnail = models.ImageField(upload_to="resources/thumbnails/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"


class ResourceFavorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resource_favorites"
    )
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="favorites"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "resource"], name="unique_favorite_per_user_resource"
            )
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.resource}"
