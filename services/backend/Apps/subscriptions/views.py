from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SubscriptionPlan, UserSubscription
from .serializers import SubscriptionPlanSerializer, UserSubscriptionSerializer


class SubscriptionPlanListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = SubscriptionPlanSerializer
    queryset = SubscriptionPlan.objects.filter(is_active=True)


class SubscriptionStatusView(APIView):
    @extend_schema(responses=UserSubscriptionSerializer)
    def get(self, request):
        subscription = (
            request.user.subscriptions.select_related("plan")
            .filter(status=UserSubscription.Status.ACTIVE)
            .first()
        )
        if subscription and subscription.expires_at and subscription.expires_at <= timezone.now():
            subscription.status = UserSubscription.Status.EXPIRED
            subscription.save(update_fields=["status"])
            subscription = None

        if subscription:
            return Response(UserSubscriptionSerializer(subscription).data)

        free_plan = SubscriptionPlan.objects.filter(is_active=True, price=0).first()
        return Response(
            {
                "plan": SubscriptionPlanSerializer(free_plan).data if free_plan else None,
                "status": "FREE",
                "started_at": None,
                "expires_at": None,
                "auto_renew": False,
            }
        )
