from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Competency
from .serializers import CompetencySerializer


class CompetencyListView(generics.ListAPIView):
    """The 6 competencies with their 30 abilities (catalog order)."""

    permission_classes = [AllowAny]
    serializer_class = CompetencySerializer
    queryset = Competency.objects.filter(is_active=True).prefetch_related("abilities")
