from django.shortcuts import render

from apps.subjects.models import Subject


def home(request):
    subjects = Subject.objects.filter(is_active=True)

    return render(
        request,
        "core/home.html",
        {
            "subjects": subjects,
        },
    )
    
def terms(request):
    return render(request, "legal/terms.html")

def privacy(request):
    return render(request, "legal/privacy.html")
