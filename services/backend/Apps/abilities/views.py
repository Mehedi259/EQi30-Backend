from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Competency
from .serializers import CompetencySerializer


class CompetencyListView(generics.ListAPIView):
    """The 6 competencies with their 30 abilities (catalog order)."""

    permission_classes = [AllowAny]
    serializer_class = CompetencySerializer
    queryset = Competency.objects.filter(is_active=True).prefetch_related("abilities")


class AbilityCompetencyView(generics.RetrieveAPIView):
    """Retrieve the parent Competency (and its abilities) for a given Ability ID."""
    
    permission_classes = [AllowAny]
    serializer_class = CompetencySerializer
    
    def get_object(self):
        ability_id = self.kwargs["ability_id"]
        from .models import Ability
        from rest_framework.exceptions import NotFound
        
        try:
            ability = Ability.objects.get(id=ability_id, is_active=True)
            return ability.competency
        except Ability.DoesNotExist:
            raise NotFound("Ability not found.")
