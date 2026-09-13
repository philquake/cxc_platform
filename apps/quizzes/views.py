from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify

from apps.subjects.models import Subject

from .models import Quiz


def quiz_queryset():
    return Quiz.objects.filter(
        is_active=True,
        lesson__is_active=True,
    ).select_related(
        "lesson__subject",
    ).prefetch_related(
        "quiz_questions__question__answers",
    )


def quiz_index(request):
    quizzes = quiz_queryset()
    return render(
        request,
        "quizzes/quiz_list.html",
        {"quizzes": quizzes},
    )


def subject_quizzes(request, subject_slug):
    subject = next(
        (
            item
            for item in Subject.objects.filter(is_active=True)
            if subject_slug in {slugify(item.name), slugify(item.code)}
        ),
        None,
    )
    if subject is None:
        raise Http404("Subject not found")

    quizzes = quiz_queryset().filter(lesson__subject=subject)
    return render(
        request,
        "quizzes/quiz_list.html",
        {"subject": subject, "quizzes": quizzes},
    )
