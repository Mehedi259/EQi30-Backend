from django.urls import path

from . import views

urlpatterns = [
    path("content/privacy-policy/", views.PrivacyPolicyView.as_view(), name="content-privacy-policy"),
    path("content/terms-of-service/", views.TermsOfServiceView.as_view(), name="content-terms-of-service"),
]
