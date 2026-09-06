from django.urls import path

from . import views

urlpatterns = [
    path("feedback/", views.SupportRequestCreateView.as_view(), name="feedback"),
]
