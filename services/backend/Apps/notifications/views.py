from rest_framework import generics

from .models import UserReminder
from .serializers import UserReminderSerializer


class UserReminderView(generics.RetrieveUpdateAPIView):
    """GET / PUT the authenticated user's reminder settings."""

    serializer_class = UserReminderSerializer
    http_method_names = ["get", "put", "options", "head"]

    def get_object(self):
        reminder, _ = UserReminder.objects.get_or_create(user=self.request.user)
        return reminder
