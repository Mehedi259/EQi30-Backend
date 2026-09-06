from django.urls import path

from . import views

urlpatterns = [
    path("subscription/plans/", views.SubscriptionPlanListView.as_view(), name="subscription-plans"),
    path("subscription/status/", views.SubscriptionStatusView.as_view(), name="subscription-status"),
]
