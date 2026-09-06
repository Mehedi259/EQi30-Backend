from django.urls import path

from . import views

urlpatterns = [
    path("abilities/", views.CompetencyListView.as_view(), name="abilities-list"),
]
