from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny

from .serializers import SupportRequestSerializer


class SupportRequestCreateView(generics.CreateAPIView):
    """Feedback / contact-support submission (attachment optional)."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = SupportRequestSerializer
