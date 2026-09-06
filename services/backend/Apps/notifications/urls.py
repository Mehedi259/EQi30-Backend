from django.urls import path

from . import views

urlpatterns = [
    path("user/reminders/", views.UserReminderView.as_view(), name="user-reminders"),
]
