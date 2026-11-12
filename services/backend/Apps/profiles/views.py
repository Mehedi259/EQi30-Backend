from rest_framework import generics

from Apps.journey.services import get_active_journey, sync_pending_today_sessions

from .models import UserProfile
from .serializers import UserProfileSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the authenticated user's profile."""

    serializer_class = UserProfileSerializer
    http_method_names = ["get", "patch", "options", "head"]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def perform_update(self, serializer):
        old_plan_id = serializer.instance.growth_plan_id
        profile = serializer.save()
        self.request.user.profile = profile
        if profile.growth_plan_id != old_plan_id:
            journey = get_active_journey(self.request.user)
            if journey is not None:
                sync_pending_today_sessions(self.request.user, journey)
