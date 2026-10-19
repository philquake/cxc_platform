from datetime import timedelta

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from apps.lessons.models import Lesson
from apps.progress.models import QuizAttempt, UserProgress
from apps.questions.models import Answer, Question

register = template.Library()

CHART_DAYS = 14


@register.simple_tag(takes_context=True)
def admin_dashboard(context):
    """Stats for the admin index. Each block is gated on the matching view permission."""
    user = context["request"].user
    today = timezone.localdate()
    week_ago = timezone.now() - timedelta(days=7)
    stats, attention, recent_attempts, chart, quick_actions = [], [], [], None, []

    if user.has_perm("auth.view_user"):
        students = get_user_model().objects.filter(is_staff=False)
        active = UserProgress.objects.filter(last_activity_date__gte=today - timedelta(days=6)).count()
        stats.append({
            "label": "Students",
            "value": students.count(),
            "hint": f"{active} active this week",
            "url": reverse("admin:auth_user_changelist"),
        })

    if user.has_perm("lessons.view_lesson"):
        lessons = Lesson.objects.all()
        stats.append({
            "label": "Published lessons",
            "value": lessons.filter(is_active=True).count(),
            "hint": f"{lessons.filter(is_active=False).count()} drafts / inactive",
            "url": reverse("admin:lessons_lesson_changelist"),
        })

    if user.has_perm("questions.view_question"):
        answered = Question.objects.filter(is_active=True).annotate(
            total=Count("attempt_answers"),
            correct=Count("attempt_answers", filter=Q(attempt_answers__is_correct=True)),
        )
        # Same thresholds as QuestionAdmin.quality_flag: below 20% or above 95% correct.
        flagged = answered.filter(total__gt=0).filter(
            Q(correct__lt=F("total") * 0.2) | Q(correct__gt=F("total") * 0.95)
        )
        no_correct = Question.objects.filter(
            is_active=True,
            format__in=[Question.FORMAT_MULTIPLE_CHOICE, Question.FORMAT_TRUE_FALSE],
        ).exclude(Exists(Answer.objects.filter(question=OuterRef("pk"), is_correct=True)))
        stats.append({
            "label": "Active questions",
            "value": answered.count(),
            "hint": f"{flagged.count()} flagged for review",
            "url": reverse("admin:questions_question_changelist"),
        })
        for question in flagged.order_by("-total")[:5]:
            attention.append({
                "title": question.text,
                "detail": f"{question.correct * 100 / question.total:.0f}% correct across {question.total} responses",
                "badge": "Too hard" if question.correct < question.total * 0.2 else "Too easy",
                "tone": "destructive" if question.correct < question.total * 0.2 else "warning",
                "url": reverse("admin:questions_question_change", args=[question.pk]),
            })
        for question in no_correct[:5]:
            attention.append({
                "title": question.text,
                "detail": f"{question.get_format_display()} with no correct answer set",
                "badge": "No answer",
                "tone": "destructive",
                "url": reverse("admin:questions_question_change", args=[question.pk]),
            })

    if user.has_perm("progress.view_quizattempt"):
        completed = QuizAttempt.objects.filter(completed_at__isnull=False)
        week = completed.filter(completed_at__gte=week_ago).aggregate(
            n=Count("id"), score=Sum("score"), total=Sum("total_questions")
        )
        stats.append({
            "label": "Quiz attempts (7d)",
            "value": week["n"],
            "hint": f"{week['score'] * 100 / week['total']:.0f}% average score" if week["total"] else "No attempts yet",
            "url": reverse("admin:progress_quizattempt_changelist"),
        })
        recent_attempts = list(completed.select_related("user", "quiz").order_by("-completed_at")[:6])

        start = today - timedelta(days=CHART_DAYS - 1)
        per_day = dict(
            completed.filter(completed_at__date__gte=start)
            .annotate(day=TruncDate("completed_at"))
            .values_list("day")
            .annotate(n=Count("id"))
        )
        peak = max(per_day.values(), default=0)
        days = []
        for offset in range(CHART_DAYS):
            day = start + timedelta(days=offset)
            n = per_day.get(day, 0)
            days.append({"day": day, "count": n, "pct": round(n * 100 / peak) if peak else 0})
        chart = {"days": days, "peak": peak, "total": sum(per_day.values())}

    for perm, label, url_name in (
        ("lessons.add_lesson", "New lesson", "admin:lessons_lesson_add"),
        ("questions.add_question", "New question", "admin:questions_question_add"),
        ("quizzes.add_quiz", "New quiz", "admin:quizzes_quiz_add"),
        ("subjects.change_subject", "Generate mock exam", "admin:subjects_subject_changelist"),
    ):
        if user.has_perm(perm):
            quick_actions.append({"label": label, "url": reverse(url_name)})

    return {
        "stats": stats,
        "attention": attention,
        "recent_attempts": recent_attempts,
        "chart": chart,
        "quick_actions": quick_actions,
    }
