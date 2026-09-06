from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Resource, ResourceFavorite


class ResourceSerializer(serializers.ModelSerializer):
    competency = serializers.SlugRelatedField(slug_field="code", read_only=True)
    is_favorited = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "description",
            "type",
            "competency",
            "file",
            "url",
            "thumbnail",
            "is_favorited",
            "created_at",
        ]


class ResourceListView(generics.ListAPIView):
    """Resources library. Filters: ?type=VIDEO&competency=<code>&favorites=true"""

    serializer_class = ResourceSerializer

    def get_queryset(self):
        qs = Resource.objects.filter(is_active=True).annotate(
            is_favorited=Exists(
                ResourceFavorite.objects.filter(
                    user=self.request.user, resource=OuterRef("pk")
                )
            )
        )
        params = self.request.query_params
        if params.get("type"):
            qs = qs.filter(type=params["type"].upper())
        if params.get("competency"):
            qs = qs.filter(competency__code=params["competency"])
        if params.get("favorites") in ("true", "1"):
            qs = qs.filter(is_favorited=True)
        return qs


class ResourceFavoriteToggleView(APIView):
    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        resource = get_object_or_404(Resource, pk=pk, is_active=True)
        favorite, created = ResourceFavorite.objects.get_or_create(
            user=request.user, resource=resource
        )
        if not created:
            favorite.delete()
        return Response({"resource_id": resource.id, "favorited": created})
