from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify
from django.db.models import Prefetch

from apps.subjects.models import Subject, Topic
from apps.progress.models import QuizAttempt

from .models import Quiz, QuizQuestion

from apps.lessons.models import Lesson

def quiz_queryset(subject=None, topic=None):
    quiz_questions = QuizQuestion.objects.filter(question__is_active=True)
    if subject is not None:
        quiz_questions = quiz_questions.filter(question__subject=subject)
    if topic is not None:
        quiz_questions = quiz_questions.filter(question__topic=topic)

    quiz_filters = {"is_active": True, "lesson__is_active": True}
    if subject is not None:
        quiz_filters["subject"] = subject
    if topic is not None:
        quiz_filters["topic"] = topic
    return Quiz.objects.filter(
        **quiz_filters,
    ).select_related(
        "lesson__subject",
        "subject",
        "topic",
    ).prefetch_related(
        Prefetch(
            "quiz_questions",
            queryset=quiz_questions.select_related("question").prefetch_related(
                "question__answers"
            ),
        ),
    )


def quiz_index(request):
    quizzes = quiz_queryset()
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {"quizzes": quizzes, "result_attempt": _result_attempt(request)},
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

    quizzes = quiz_queryset(subject=subject)
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {"subject": subject, "quizzes": quizzes, "result_attempt": _result_attempt(request)},
    )


def lesson_quizzes(request, lesson_id):
    quizzes = quiz_queryset().filter(lesson_id=lesson_id)
    if not quizzes.exists():
        raise Http404("Quiz not found")
    quizzes = list(quizzes)
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {
            "subject": quizzes[0].subject,
            "topic": quizzes[0].topic,
            "quizzes": quizzes,
            "result_attempt": _result_attempt(request),
        },
    )


def quiz_detail(request, quiz_id):
    quizzes = quiz_queryset().filter(pk=quiz_id)
    quiz = quizzes.first()
    if quiz is None:
        raise Http404("Quiz not found")
    _add_latest_attempts(request, [quiz])
    return render(
        request,
        "quizzes/quiz_list.html",
        {
            "subject": quiz.subject,
            "topic": quiz.topic,
            "quizzes": [quiz],
            "result_attempt": _result_attempt(request),
            "next_lesson": Lesson.objects.filter(
                subject=quiz.subject,
                is_active=True,
                lesson_number__gt=quiz.lesson.lesson_number,
            ).order_by("lesson_number", "section_number").first(),
            "medium_quiz": Quiz.objects.filter(
                subject=quiz.subject,
                topic=quiz.topic,
                is_active=True,
                title__icontains="medium",
            ).exclude(pk=quiz.pk).first(),
        },
    )


def topic_quizzes(request, subject_slug, topic_slug):
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

    topic = Topic.objects.filter(
        subject=subject,
        slug=topic_slug,
        is_active=True,
    ).first()
    if topic is None:
        raise Http404("Topic not found")

    quizzes = quiz_queryset(subject=subject, topic=topic)
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {
            "subject": subject,
            "topic": topic,
            "quizzes": quizzes,
            "result_attempt": _result_attempt(request),
        },
    )


def _add_latest_attempts(request, quizzes):
    if not request.user.is_authenticated:
        return
    latest_attempts = {}
    for quiz in quizzes:
        latest_attempts[quiz.id] = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz,
            completed_at__isnull=False,
        ).order_by("-completed_at").first()
    for quiz in quizzes:
        quiz.latest_attempt = latest_attempts.get(quiz.id)


def _result_attempt(request):
    attempt_id = request.GET.get("attempt")
    if not request.user.is_authenticated or not attempt_id or not attempt_id.isdigit():
        return None
    return QuizAttempt.objects.filter(
        id=int(attempt_id),
        user=request.user,
        completed_at__isnull=False,
    ).select_related("quiz").first()
