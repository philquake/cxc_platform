import math
import random
import time

from django.core import signing
from django.http import Http404
from django.shortcuts import render
from django.db.models import Count, Prefetch, Q

from apps.accounts.models import Profile
from apps.subjects.lookup import get_subject_or_404
from apps.subjects.models import Topic
from apps.progress.models import QuizAttempt

from .models import Quiz, QuizQuestion
from .services import attach_draw_counts, draw_lesson_questions

from apps.lessons.models import Lesson

def quiz_queryset(subject=None, topic=None, with_questions=False):
    quiz_questions = QuizQuestion.objects.filter(question__is_active=True)
    if subject is not None:
        quiz_questions = quiz_questions.filter(question__subject=subject)
    if topic is not None:
        quiz_questions = quiz_questions.filter(question__topic=topic)


    quiz_filters = Q(is_active=True, subject__is_active=True) & (Q(lesson__is_active=True) | Q(is_mock=True))
    if subject is not None:
        quiz_filters &= Q(subject=subject)
    if topic is not None:
        quiz_filters &= Q(topic=topic)
    quizzes = Quiz.objects.filter(
        quiz_filters,
    ).select_related(
        "lesson__subject",
        "subject",
        "topic",
    )
    if not with_questions:
        # Listings only show a count; questions and answers load in quiz_detail.
        question_filter = Q(quiz_questions__question__is_active=True)
        if subject is not None:
            question_filter &= Q(quiz_questions__question__subject=subject)
        if topic is not None:
            question_filter &= Q(quiz_questions__question__topic=topic)
        return quizzes.annotate(question_count=Count("quiz_questions", filter=question_filter))
    return quizzes.prefetch_related(
        Prefetch(
            # Fixed "order" here; _shuffle_questions randomises quizzes that ask for it.
            "quiz_questions",
            to_attr="question_list",
            queryset=quiz_questions.select_related("question").prefetch_related(
                "question__answers"
            ),
        ),
    )


def quiz_index(request):
    quizzes = list(quiz_queryset())
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {"quizzes": quizzes, "result_attempt": _result_attempt(request)},
    )


def subject_quizzes(request, subject_slug):
    subject = get_subject_or_404(subject_slug)

    quizzes = list(quiz_queryset(subject=subject))
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {"subject": subject, "quizzes": quizzes, "result_attempt": _result_attempt(request)},
    )


def lesson_quizzes(request, lesson_id):
    quizzes = quiz_queryset(with_questions=True).filter(lesson_id=lesson_id)
    if not quizzes.exists():
        raise Http404("Quiz not found")
    quizzes = list(quizzes)
    _shuffle_questions(quizzes)
    _draw_auto(request, quizzes)
    _add_latest_attempts(request, quizzes)
    return render(
        request,
        "quizzes/quiz_list.html",
        {
            "subject": quizzes[0].subject,
            "topic": quizzes[0].topic,
            "quizzes": quizzes,
            "show_questions": True,
            "result_attempt": _result_attempt(request),
        },
    )


def quiz_detail(request, quiz_id):
    quizzes = quiz_queryset(with_questions=True).filter(pk=quiz_id)
    quiz = quizzes.first()
    if quiz is None:
        raise Http404("Quiz not found")
    _shuffle_questions([quiz])
    _draw_auto(request, [quiz])
    _add_latest_attempts(request, [quiz])
    return render(
        request,
        "quizzes/quiz_list.html",
        {
            "subject": quiz.subject,
            "topic": quiz.topic,
            "quizzes": [quiz],
            "show_questions": True,
            "result_attempt": _result_attempt(request),
            # Same order as the lesson reader: unit (section) first, then lesson number.
            "next_lesson": Lesson.objects.filter(
                Q(section_number__gt=quiz.lesson.section_number)
                | Q(section_number=quiz.lesson.section_number, lesson_number__gt=quiz.lesson.lesson_number),
                subject=quiz.subject,
                is_active=True,
            ).order_by("section_number", "lesson_number", "title").first() if quiz.lesson_id else None,
            "other_quiz": Quiz.objects.filter(
                subject=quiz.subject,
                topic=quiz.topic,
                is_active=True,
                is_mock=False,
                lesson__is_active=True,
            ).exclude(pk=quiz.pk).first() if quiz.topic_id else None,
        },
    )


def topic_quizzes(request, subject_slug, topic_slug):
    subject = get_subject_or_404(subject_slug)

    topic = Topic.objects.filter(
        subject=subject,
        slug=topic_slug,
        is_active=True,
    ).first()
    if topic is None:
        raise Http404("Topic not found")

    quizzes = list(quiz_queryset(subject=subject, topic=topic))
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


def _add_time_limits(request, quizzes):
    """Set quiz.effective_time_limit_minutes, applying the student's time multiplier."""
    multiplier = 1
    if request.user.is_authenticated:
        multiplier = (
            Profile.objects.filter(user=request.user)
            .values_list("time_multiplier", flat=True)
            .first()
            or 1
        )
    for quiz in quizzes:
        minutes = quiz.time_limit_minutes
        quiz.effective_time_limit_minutes = (
            math.ceil(minutes * multiplier) if minutes else minutes
        )
        quiz.has_extra_time = bool(minutes) and quiz.effective_time_limit_minutes > minutes
        if quiz.is_mock and request.user.is_authenticated:
            quiz.start_token = signing.dumps([quiz.id, request.user.id, int(time.time())])


def _shuffle_questions(quizzes):
    for quiz in quizzes:
        if quiz.shuffle_questions:
            random.shuffle(quiz.question_list)


def _draw_auto(request, quizzes):
    """Auto-draw quizzes get a fresh set per page load; the chosen ids are signed so scoring uses exactly them."""
    for quiz in quizzes:
        if quiz.auto_draw:
            quiz.question_list = draw_lesson_questions(request.user, quiz)
            quiz.draw_token = signing.dumps([quiz.id, request.user.id or 0, [qq.question.id for qq in quiz.question_list]])


def latest_attempts_by_quiz(user, quizzes):
    """{quiz_id: the user's most recently completed attempt} for the given quizzes."""
    latest = {}
    for attempt in QuizAttempt.objects.filter(
        user=user,
        quiz_id__in=[quiz.id for quiz in quizzes],
        completed_at__isnull=False,
    ).order_by("-completed_at"):
        latest.setdefault(attempt.quiz_id, attempt)
    return latest


def _add_latest_attempts(request, quizzes):
    _add_time_limits(request, quizzes)
    attach_draw_counts([quiz for quiz in quizzes if not hasattr(quiz, "question_list")])
    if not request.user.is_authenticated:
        return
    latest_attempts = latest_attempts_by_quiz(request.user, quizzes)
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
	).select_related("quiz").prefetch_related(
		"answers__question__answers",
		"answers__selected_answer",
	).first()
