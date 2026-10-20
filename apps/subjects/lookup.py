from django.http import Http404

from .models import Subject


def get_subject_or_404(slug, queryset=None):
    """Find an active subject by its slug; the subject code is accepted as a fallback."""
    subjects = (Subject.objects if queryset is None else queryset).filter(is_active=True)
    subject = subjects.filter(slug=slug).first() or subjects.filter(code__iexact=slug).first()
    if subject is None:
        raise Http404("Subject not found")
    return subject
