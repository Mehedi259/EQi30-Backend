from django.urls import path

from . import views

urlpatterns = [
    path("home/dashboard/", views.HomeDashboardView.as_view(), name="home-dashboard"),
    path("progress/tracker/", views.ProgressTrackerView.as_view(), name="progress-tracker"),
]
