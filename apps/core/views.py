from django.db import connection
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import render

from apps.lessons.models import Lesson
from apps.questions.models import Question
from apps.subjects.models import Subject

try:
    from django.contrib.postgres.search import SearchQuery, SearchRank
except ImportError:  # pragma: no cover
    SearchQuery = SearchRank = None

from .search import SEARCH_CONFIG, lesson_search_vector, question_search_vector


def home(request):
    # Subqueries, not two Counts: joining lessons and questions together multiplies the rows (lessons x questions).
    def count_of(model):
        return Coalesce(Subquery(
            model.objects.filter(subject=OuterRef("pk"), is_active=True)
            .order_by().values("subject").annotate(n=Count("pk")).values("n")
        ), 0)

    subjects = Subject.objects.filter(is_active=True).annotate(
        lesson_count=count_of(Lesson),
        question_count=count_of(Question),
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
        lessons = Lesson.objects.filter(is_active=True, subject__is_active=True).defer("content")
        questions = Question.objects.filter(is_active=True, subject__is_active=True, lesson__is_active=True)
        if connection.vendor == "postgresql" and SearchQuery is not None:
            search_query = SearchQuery(query_text, config=SEARCH_CONFIG)
            # Match with @@ on the same vector the GIN indexes cover (lessons/0005, questions/0006); rank only the hits.
            lesson_vector = lesson_search_vector()
            lessons = lessons.annotate(
                search=lesson_vector, rank=SearchRank(lesson_vector, search_query)
            ).filter(search=search_query).select_related("subject").order_by("-rank")[:20]
            question_vector = question_search_vector()
            questions = questions.annotate(
                search=question_vector, rank=SearchRank(question_vector, search_query)
            ).filter(search=search_query).select_related("subject", "topic", "lesson").order_by("-rank")[:20]
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
