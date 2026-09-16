from django.urls import path

from . import views


app_name = "progress"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path(
        "lessons/<int:lesson_id>/complete/",
        views.complete_lesson,
        name="complete-lesson",
    ),
    path("quizzes/<int:quiz_id>/submit/", views.submit_quiz, name="submit-quiz"),
]
