from django.urls import path

from . import views


app_name = "quizzes"

urlpatterns = [
    path("", views.quiz_index, name="list"),
    path("lesson/<int:lesson_id>/", views.lesson_quizzes, name="lesson-list"),
    path("detail/<int:quiz_id>/", views.quiz_detail, name="detail"),
    path(
        "<slug:subject_slug>/<slug:topic_slug>/",
        views.topic_quizzes,
        name="topic-list",
    ),
    path("<slug:subject_slug>/", views.subject_quizzes, name="subject-list"),
]