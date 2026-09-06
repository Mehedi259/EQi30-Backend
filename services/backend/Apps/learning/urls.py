from django.urls import path

from . import views

urlpatterns = [
    path(
        "abilities/<int:ability_id>/days/<int:day_number>/",
        views.AbilityDayContentView.as_view(),
        name="ability-day-content",
    ),
    path("sessions/<int:pk>/complete/", views.CompleteSessionView.as_view(), name="session-complete"),
    path("sessions/<int:pk>/reflection/", views.SessionReflectionView.as_view(), name="session-reflection"),
    path("check-ins/weekly/", views.WeeklyCheckInView.as_view(), name="weekly-checkin"),
]
