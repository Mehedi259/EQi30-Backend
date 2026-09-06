from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LegalDocument
from .serializers import LegalDocumentSerializer


class _LegalDocumentView(APIView):
    permission_classes = [AllowAny]
    document_type = None

    @extend_schema(responses=LegalDocumentSerializer)
    def get(self, request):
        document = (
            LegalDocument.objects.filter(type=self.document_type, is_active=True)
            .order_by("-published_at")
            .first()
        )
        if document is None:
            raise NotFound("Document is not published yet.")
        return Response(LegalDocumentSerializer(document).data)


class PrivacyPolicyView(_LegalDocumentView):
    document_type = LegalDocument.DocumentType.PRIVACY_POLICY


class TermsOfServiceView(_LegalDocumentView):
    document_type = LegalDocument.DocumentType.TERMS_OF_SERVICE
