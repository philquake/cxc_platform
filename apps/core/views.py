from django.db import connection
from django.db.models import Q
from django.shortcuts import render

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.subjects.models import Subject

try:
    from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
except ImportError:  # pragma: no cover
    SearchQuery = SearchRank = SearchVector = None


def home(request):
    subjects = Subject.objects.filter(is_active=True)

    return render(
        request,
        "core/home.html",
        {
            "subjects": subjects,
        },
    )


def search(request):
    query_text = (request.GET.get("q") or "").strip()
    lesson_results = []
    question_results = []

    if query_text:
        if connection.vendor == "postgresql" and SearchVector is not None:
            search_query = SearchQuery(query_text)
            lessons = Lesson.objects.filter(is_active=True).annotate(
                rank=SearchRank(
                    SearchVector("title", weight="A") + SearchVector("content", weight="B"),
                    search_query,
                )
            ).filter(rank__gt=0).select_related("subject").order_by("-rank")[:20]
            questions = Question.objects.filter(is_active=True).annotate(
                rank=SearchRank(SearchVector("text", weight="A"), search_query)
            ).filter(rank__gt=0).select_related("subject", "topic", "lesson").order_by("-rank")[:20]
        else:
            lessons = Lesson.objects.filter(
                is_active=True,
            ).filter(
                Q(title__icontains=query_text) | Q(content__icontains=query_text),
            ).select_related("subject").order_by("title")[:20]
            questions = Question.objects.filter(
                is_active=True,
            ).filter(
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


def terms(request):
    return render(request, "legal/terms.html")


def privacy(request):
    return render(request, "legal/privacy.html")
