from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.db.models import Prefetch

from apps.lessons.models import Lesson
from apps.quizzes.models import Quiz
from apps.progress.models import LessonProgress, QuizAttempt
from .models import Subject


def subject_list(request):
    subjects = Subject.objects.filter(is_active=True)

    return render(
        request,
        "subjects/subject_list.html",
        {"subjects": subjects},
    )


def subject_detail(request, slug):
    subjects = Subject.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "lessons",
            queryset=Lesson.objects.filter(is_active=True).order_by(
                "section_number", "lesson_number", "title"
            ),
            to_attr="active_lessons",
        )
    )
    subject = next(
        (item for item in subjects if slug in {slugify(item.name), slugify(item.code)}),
        None,
    )
    if subject is None:
        raise Http404("Subject not found")

    completed_ids = set()
    if request.user.is_authenticated:
        completed_ids = set(
            LessonProgress.objects.filter(
                user=request.user,
                completed=True,
                lesson__subject=subject,
            ).values_list("lesson_id", flat=True)
        )
    lessons = subject.active_lessons
    return render(
        request,
        "subjects/subject_detail.html",
        {
            "subject": subject,
            "completed_ids": completed_ids,
            "lesson_total": len(lessons),
            "lesson_done": sum(1 for lesson in lessons if lesson.id in completed_ids),
            "next_lesson": next((l for l in lessons if l.id not in completed_ids), None)
            if request.user.is_authenticated
            else None,
        },
    )


def lesson_detail(request, subject_slug, lesson_slug):
    subject = get_object_or_404(Subject, name__iexact=subject_slug.replace("-", " "), is_active=True)
    lesson = get_object_or_404(
        Lesson.objects,
        subject=subject,
        slug=lesson_slug,
        is_active=True,
    )

    quizzes = Quiz.objects.filter(
        lesson=lesson,
        is_active=True,
    ).prefetch_related(
        "quiz_questions__question__answers"
    )
    lesson_progress = None
    latest_attempts = {}
    if request.user.is_authenticated:
        lesson_progress = LessonProgress.objects.filter(
            user=request.user,
            lesson=lesson,
            completed=True,
        ).first()
        latest_attempts = {
            quiz.id: QuizAttempt.objects.filter(
                user=request.user,
                quiz=quiz,
                completed_at__isnull=False,
            ).order_by("-completed_at").first()
            for quiz in quizzes
        }
        for quiz in quizzes:
            quiz.latest_attempt = latest_attempts[quiz.id]

    ordered = list(
        Lesson.objects.filter(subject=subject, is_active=True).order_by(
            "section_number", "lesson_number", "title"
        )
    )
    position = next((i for i, item in enumerate(ordered) if item.pk == lesson.pk), None)
    previous_lesson = ordered[position - 1] if position else None
    next_lesson = (
        ordered[position + 1]
        if position is not None and position + 1 < len(ordered)
        else None
    )

    return render(
        request,
        "subjects/lesson_detail.html",
        {
            "subject": subject,
            "lesson": lesson,
            "quizzes": quizzes,
            "lesson_progress": lesson_progress,
            "previous_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "lesson_position": position + 1 if position is not None else None,
            "lesson_total": len(ordered),
        },
    )