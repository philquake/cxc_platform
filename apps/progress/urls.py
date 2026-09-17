from django.urls import path

from . import views


app_name = "progress"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "leaderboard/<slug:subject_slug>/",
        views.subject_leaderboard,
        name="subject-leaderboard",
    ),
    path(
        "leaderboard/<slug:subject_slug>/<slug:topic_slug>/",
        views.leaderboard,
        name="leaderboard",
    ),
    path(
        "lessons/<int:lesson_id>/complete/",
        views.complete_lesson,
        name="complete-lesson",
    ),
    path("quizzes/<int:quiz_id>/submit/", views.submit_quiz, name="submit-quiz"),
]
