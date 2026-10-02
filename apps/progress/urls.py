from django.urls import path

from . import views


app_name = "progress"

urlpatterns = [
    path(
        "study-plan/<slug:subject_slug>/",
        views.study_plan_view,
        name="study-plan",
    ),
    path("", 
        views.dashboard,
        name="dashboard"),
    
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
    
    path("quizzes/<int:quiz_id>/submit/",
        views.submit_quiz,
        name="submit-quiz"),
    
    path("mistakes/",
        views.mistake_bank,
        name="mistake-bank"),

    path(
        "flashcards/review/",
        views.review_flashcard,
        name="review-flashcard",
    ),
    path(
        "flashcards/<slug:subject_slug>/",
        views.flashcard_session,
        name="flashcards",
    ),
    path(
        "flashcards/<slug:subject_slug>/<slug:topic_slug>/",
        views.flashcard_session,
        name="flashcards-topic",
    ),
]
