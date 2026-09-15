from django.urls import path

from . import views

urlpatterns = [
    path("abilities/", views.CompetencyListView.as_view(), name="abilities-list"),
    path("abilities/<int:ability_id>/competency/", views.AbilityCompetencyView.as_view(), name="ability-competency"),
]
