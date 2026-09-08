from django.http import Http404
from django.shortcuts import render
from django.utils.text import slugify

from .models import Subject


def subject_list(request):
    subjects = Subject.objects.filter(is_active=True)

    return render(
        request,
        "subjects/subject_list.html",
        {"subjects": subjects},
    )


def subject_detail(request, slug):
    subjects = Subject.objects.filter(is_active=True)
    subject = next(
        (
            item
            for item in subjects
            if slug in {slugify(item.name), slugify(item.code)}
        ),
        None,
    )

    if subject is None:
        raise Http404("Subject not found")

    return render(
        request,
        "subjects/subject_detail.html",
        {"subject": subject},
    )