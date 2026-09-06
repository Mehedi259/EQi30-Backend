from django.urls import path

from . import views

urlpatterns = [
    path("resources/", views.ResourceListView.as_view(), name="resources-list"),
    path("resources/<int:pk>/favorite/", views.ResourceFavoriteToggleView.as_view(), name="resource-favorite"),
]
