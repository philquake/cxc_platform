from django.http import Http404
from django.utils.text import slugify

from .models import Subject


def get_subject_or_404(slug):
    """Subjects are addressed by slugified name or code (no slug field)."""
    for item in Subject.objects.filter(is_active=True):
        if slug in {slugify(item.name), slugify(item.code)}:
            return item
    raise Http404("Subject not found")
