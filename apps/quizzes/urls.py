from django.urls import path

from . import views


app_name = "quizzes"

urlpatterns = [
    path("", views.quiz_index, name="list"),
    path("<slug:subject_slug>/", views.subject_quizzes, name="subject-list"),
]