from django.urls import path

from . import views

urlpatterns = [
    # Anonymous onboarding
    path("onboarding/session/", views.OnboardingSessionCreateView.as_view(), name="onboarding-session"),
    path("onboarding/<uuid:session_uuid>/assessment/", views.OnboardingAssessmentView.as_view(), name="onboarding-assessment"),
    path("onboarding/<uuid:session_uuid>/priorities/", views.OnboardingPrioritiesView.as_view(), name="onboarding-priorities"),
    path("onboarding/<uuid:session_uuid>/growth-plan/", views.OnboardingGrowthPlanView.as_view(), name="onboarding-growth-plan"),
    path("onboarding/<uuid:session_uuid>/practice-time/", views.OnboardingPracticeTimeView.as_view(), name="onboarding-practice-time"),
    # Onboarding catalogs
    path("growth-plans/", views.GrowthPlanListView.as_view(), name="growth-plans"),
    path("practice-times/", views.PracticeTimeListView.as_view(), name="practice-times"),
    path("guided-journey/", views.GuidedJourneyListView.as_view(), name="guided-journey"),
    # Personalized journey
    path("journey/", views.JourneyView.as_view(), name="journey"),
    path("journey/today/", views.JourneyTodayView.as_view(), name="journey-today"),
    path("journey/history/", views.JourneyHistoryView.as_view(), name="journey-history"),
]
