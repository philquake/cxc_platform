from django.contrib import admin

from .models import (
    LessonProgress,
    QuizAttempt,
    QuizAnswer,
)


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "lesson",
        "completed",
        "completed_at",
        "updated_at",
    )
    list_filter = (
        "completed",
        "lesson__topic__subject",
    )
    search_fields = (
        "user__username",
        "lesson__title",
    )


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "quiz",
        "score",
        "total_questions",
        "started_at",
        "completed_at",
    )
    list_filter = ("quiz",)
    search_fields = (
        "user__username",
        "quiz__title",
    )


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "selected_answer",
        "is_correct",
    )
    list_filter = ("is_correct",)