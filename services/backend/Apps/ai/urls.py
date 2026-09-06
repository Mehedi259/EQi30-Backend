from django.urls import path
from .views import AssessmentAnalyzeView, JourneyRecommendView, ChatRespondView

urlpatterns = [
    path('assessment/analyze/', AssessmentAnalyzeView.as_view(), name='ai-assessment-analyze'),
    path('journey/recommend/', JourneyRecommendView.as_view(), name='ai-journey-recommend'),
    path('chat/respond/', ChatRespondView.as_view(), name='ai-chat-respond'),
]
