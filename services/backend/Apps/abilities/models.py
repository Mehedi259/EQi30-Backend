from django.db import models


class Competency(models.Model):
    """One of the 6 EQ competencies (e.g. Self-Management)."""

    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to="competencies/icons/", null=True, blank=True)
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Fallback order when the user has no personalized priority."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name_plural = "competencies"

    def __str__(self):
        return self.name


class Ability(models.Model):
    """One of the 30 abilities (5 per competency)."""

    competency = models.ForeignKey(
        Competency, on_delete=models.CASCADE, related_name="abilities"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to="abilities/icons/", null=True, blank=True)
    default_order = models.PositiveSmallIntegerField(
        default=0, help_text="Order of the ability inside its competency."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["default_order", "id"]
        verbose_name_plural = "abilities"
        constraints = [
            models.UniqueConstraint(
                fields=["competency", "name"], name="unique_ability_name_per_competency"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.competency.name})"
