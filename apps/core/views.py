from django.db import connection
from django.db.models import Count, Q
from django.shortcuts import render

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.subjects.models import Subject

try:
    from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
except ImportError:  # pragma: no cover
    SearchQuery = SearchRank = SearchVector = None


def home(request):
    subjects = Subject.objects.filter(is_active=True).annotate(
        lesson_count=Count("lessons", filter=Q(lessons__is_active=True), distinct=True),
        question_count=Count("questions", filter=Q(questions__is_active=True), distinct=True),
    )

    return render(
        request,
        "core/home.html",
        {
            "subjects": subjects,
            "lesson_max": max((s.lesson_count for s in subjects), default=0),
        },
    )


def search(request):
    query_text = (request.GET.get("q") or "").strip()
    lesson_results = []
    question_results = []

    if query_text:
        # Only content whose lesson page is public, so every result link works.
        lessons = Lesson.objects.filter(is_active=True, subject__is_active=True)
        questions = Question.objects.filter(is_active=True, subject__is_active=True, lesson__is_active=True)
        if connection.vendor == "postgresql" and SearchVector is not None:
            search_query = SearchQuery(query_text)
            lessons = lessons.annotate(
                rank=SearchRank(
                    SearchVector("title", weight="A") + SearchVector("content", weight="B"),
                    search_query,
                )
            ).filter(rank__gt=0).select_related("subject").order_by("-rank")[:20]
            questions = questions.annotate(
                rank=SearchRank(
                    SearchVector("text", weight="A") + SearchVector("explanation", weight="B"),
                    search_query,
                )
            ).filter(rank__gt=0).select_related("subject", "topic", "lesson").order_by("-rank")[:20]
        else:
            lessons = lessons.filter(
                Q(title__icontains=query_text) | Q(content__icontains=query_text),
            ).select_related("subject").order_by("title")[:20]
            questions = questions.filter(
                Q(text__icontains=query_text) | Q(explanation__icontains=query_text),
            ).select_related("subject", "topic", "lesson").order_by("text")[:20]

        lesson_results = list(lessons)
        question_results = list(questions)

    return render(
        request,
        "core/search.html",
        {
            "query": query_text,
            "lesson_results": lesson_results,
            "question_results": question_results,
        },
    )


def tools_index(request):
    return render(request, "core/tools.html")


def binary_converter(request):
    return render(request, "core/binary_converter.html")


def about(request):
    return render(request, "core/about.html")


def terms(request):
    return render(request, "legal/terms.html")


def privacy(request):
    return render(request, "legal/privacy.html")
