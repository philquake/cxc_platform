from django.shortcuts import get_object_or_404, render
from django.db.models import Count, Prefetch, Q

from apps.lessons.models import Lesson
from apps.quizzes.models import Quiz
from apps.progress.models import LessonProgress, QuizAnswer, QuizAttempt, percent
from apps.questions.models import Question
from apps.quizzes.services import attach_draw_counts
from apps.quizzes.views import latest_attempts_by_quiz
from .lookup import get_subject_or_404
from .models import Subject

MASTERY_LEVELS = (
    (100, "mastered", "Mastered"),
    (80, "proficient", "Proficient"),
    (60, "familiar", "Familiar"),
    (0, "attempted", "Attempted"),
)


def _lesson_coverage(user, lessons):
    """{lesson_id: (questions answered and marked, active questions)} so mastery can reflect how much of the bank was seen."""
    pool = dict(
        Question.objects.filter(lesson__in=lessons, is_active=True).values_list("lesson_id").annotate(n=Count("id"))
    )
    seen = dict(
        QuizAnswer.objects.filter(
            attempt__user=user, question__lesson__in=lessons, question__is_active=True, marks_awarded__isnull=False
        ).values_list("question__lesson_id").annotate(n=Count("question", distinct=True))
    )
    return {lesson.id: (seen.get(lesson.id, 0), pool.get(lesson.id, 0)) for lesson in lessons}


def _lesson_mastery(user, lessons):
    """Attach mastery_level/label/step (0-4) from the best quiz score per lesson, capped by how much of the bank was answered.

    Under 40% of the lesson's questions answered caps at Familiar, under 70% at Proficient, and Mastered also
    needs a perfect score on a quiz that was not Easy, so a short easy quiz cannot stand in for the whole lesson.
    """
    best, best_hard, coverage = {}, {}, {}
    if user.is_authenticated:
        rows = QuizAttempt.objects.filter(
            user=user,
            quiz__lesson__in=lessons,
            completed_at__isnull=False,
            awaiting_review=False,
            total_marks__gt=0,
        ).values_list("quiz__lesson_id", "score", "total_marks", "quiz__difficulty")
        for lesson_id, score, total, difficulty in rows:
            best[lesson_id] = max(best.get(lesson_id, 0), percent(score, total))
            if difficulty != "easy":
                best_hard[lesson_id] = max(best_hard.get(lesson_id, 0), percent(score, total))
        coverage = _lesson_coverage(user, lessons)
    for lesson in lessons:
        lesson.mastery_level, lesson.mastery_label, lesson.mastery_step = "none", "Not started", 0
        lesson.coverage_seen, lesson.coverage_total = coverage.get(lesson.id, (0, 0))
        if lesson.id in best:
            for index, (floor, level, label) in enumerate(MASTERY_LEVELS):
                if best[lesson.id] >= floor:
                    lesson.mastery_level, lesson.mastery_label = level, label
                    lesson.mastery_step = 4 - index
                    break
            share = lesson.coverage_seen / lesson.coverage_total if lesson.coverage_total else 1
            cap = 2 if share < 0.4 else 3 if share < 0.7 else 4
            if best_hard.get(lesson.id, 0) < 100:
                cap = min(cap, 3)
            if lesson.mastery_step > cap:
                lesson.mastery_step = cap
                _, lesson.mastery_level, lesson.mastery_label = MASTERY_LEVELS[4 - cap]


def _units(lessons, completed_ids):
    """Group ordered lessons into syllabus units (by section_number) with progress counts."""
    units = []
    for lesson in lessons:
        if not units or units[-1]["number"] != lesson.section_number:
            units.append({"number": lesson.section_number, "title": lesson.section_title, "lessons": []})
        units[-1]["lessons"].append(lesson)
    for unit in units:
        unit["total"] = len(unit["lessons"])
        unit["done"] = sum(1 for lesson in unit["lessons"] if lesson.id in completed_ids)
        unit["percent"] = round(unit["done"] * 100 / unit["total"])
        unit["mastered"] = sum(1 for lesson in unit["lessons"] if lesson.mastery_step >= 3)
    return units


def subject_list(request):
    subjects = Subject.objects.filter(is_active=True).annotate(
        lesson_count=Count("lessons", filter=Q(lessons__is_active=True))
    )

    return render(
        request,
        "subjects/subject_list.html",
        {"subjects": subjects},
    )


def subject_detail(request, slug):
    subject = get_subject_or_404(slug, Subject.objects.prefetch_related(
        Prefetch(
            "lessons",
            queryset=Lesson.objects.filter(is_active=True).order_by(
                "section_number", "lesson_number", "title"
            ),
            to_attr="active_lessons",
        )
    ))

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
    _lesson_mastery(request.user, lessons)
    units = _units(lessons, completed_ids)
    next_lesson = next((l for l in lessons if l.id not in completed_ids), None) if request.user.is_authenticated else None
    open_unit = next(
        (unit["number"] for unit in units if next_lesson and next_lesson in unit["lessons"]),
        units[0]["number"] if units else None,
    )
    return render(
        request,
        "subjects/subject_detail.html",
        {
            "subject": subject,
            "completed_ids": completed_ids,
            "lesson_total": len(lessons),
            "lesson_done": sum(1 for lesson in lessons if lesson.id in completed_ids),
            "next_lesson": next_lesson,
            "units": units,
            "open_unit": open_unit,
            "mastered_total": sum(1 for lesson in lessons if lesson.mastery_step >= 3),
            "lesson_percent": round(sum(1 for l in lessons if l.id in completed_ids) * 100 / len(lessons)) if lessons else 0,
        },
    )


def lesson_detail(request, subject_slug, lesson_slug):
    subject = get_subject_or_404(subject_slug)
    lesson = get_object_or_404(
        Lesson.objects,
        subject=subject,
        slug=lesson_slug,
        is_active=True,
    )

    quizzes = list(Quiz.objects.filter(
        lesson=lesson,
        is_active=True,
    ).annotate(
        question_count=Count("quiz_questions", filter=Q(quiz_questions__question__is_active=True))
    ))
    attach_draw_counts(quizzes)
    lesson_progress = None
    if request.user.is_authenticated:
        lesson_progress = LessonProgress.objects.filter(
            user=request.user,
            lesson=lesson,
            completed=True,
        ).first()
        latest_attempts = latest_attempts_by_quiz(request.user, quizzes)
        for quiz in quizzes:
            quiz.latest_attempt = latest_attempts.get(quiz.id)

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

    completed_ids = set()
    if request.user.is_authenticated:
        completed_ids = set(
            LessonProgress.objects.filter(
                user=request.user, completed=True, lesson__subject=subject
            ).values_list("lesson_id", flat=True)
        )
    _lesson_mastery(request.user, ordered)
    unit = next(
        (u for u in _units(ordered, completed_ids) if u["number"] == lesson.section_number),
        None,
    )

    return render(
        request,
        "subjects/lesson_detail.html",
        {
            "subject": subject,
            "lesson": lesson,
            "unit": unit,
            "completed_ids": completed_ids,
            "quizzes": quizzes,
            "lesson_progress": lesson_progress,
            "previous_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "lesson_position": position + 1 if position is not None else None,
            "lesson_total": len(ordered),
        },
    )