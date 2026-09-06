from django.db import models


class LegalDocument(models.Model):
    class DocumentType(models.TextChoices):
        PRIVACY_POLICY = "PRIVACY_POLICY", "Privacy Policy"
        TERMS_OF_SERVICE = "TERMS_OF_SERVICE", "Terms of Service"

    type = models.CharField(max_length=30, choices=DocumentType.choices)
    title = models.CharField(max_length=200)
    content = models.TextField()
    version = models.CharField(max_length=20, default="1.0")
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.get_type_display()} v{self.version}"
