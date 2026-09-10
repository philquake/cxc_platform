from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.db.models import Prefetch

from apps.lessons.models import Lesson
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

    return render(
        request,
        "subjects/subject_detail.html",
        {"subject": subject},
    )


def lesson_detail(request, subject_slug, lesson_slug):
    subject = get_object_or_404(Subject, name__iexact=subject_slug.replace("-", " "), is_active=True)
    lesson = get_object_or_404(
        Lesson.objects,
        subject=subject,
        slug=lesson_slug,
        is_active=True,
    )

    return render(
        request,
        "subjects/lesson_detail.html",
        {"subject": subject, "lesson": lesson},
    )