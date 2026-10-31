from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny

from .models import Ability, Competency
from .serializers import AbilityJourneyIntroSerializer, CompetencySerializer


class CompetencyListView(generics.ListAPIView):
    """The 6 competencies with their 30 abilities (catalog order)."""

    permission_classes = [AllowAny]
    serializer_class = CompetencySerializer
    queryset = Competency.objects.filter(is_active=True).prefetch_related("abilities")


class AbilityCompetencyView(generics.RetrieveAPIView):
    """Retrieve the Ability journey intro details and its competency context for a given Ability ID."""
    
    permission_classes = [AllowAny]
    serializer_class = AbilityJourneyIntroSerializer
    
    def get_object(self):
        ability_id = self.kwargs["ability_id"]
        try:
            return (
                Ability.objects
                .select_related("competency")
                .prefetch_related("competency__abilities", "day_contents")
                .get(id=ability_id, is_active=True)
            )
        except Ability.DoesNotExist:
            raise NotFound("Ability not found.")

