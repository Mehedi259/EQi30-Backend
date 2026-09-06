from rest_framework import generics

from .models import UserProfile
from .serializers import UserProfileSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the authenticated user's profile."""

    serializer_class = UserProfileSerializer
    http_method_names = ["get", "patch", "options", "head"]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
