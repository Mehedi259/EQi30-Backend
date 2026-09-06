from django.conf import settings
from django.db import models


class SupportRequest(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_requests",
    )
    subject = models.CharField(max_length=200)
    email = models.EmailField()
    message = models.TextField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.subject}"


class SupportAttachment(models.Model):
    support_request = models.ForeignKey(
        SupportRequest, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="support_attachments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for request {self.support_request_id}"
