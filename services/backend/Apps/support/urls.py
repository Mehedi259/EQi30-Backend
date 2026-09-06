from django.urls import path

from . import views

urlpatterns = [
    path("content/faqs/", views.FAQListView.as_view(), name="content-faqs"),
]
