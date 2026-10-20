import re
import nh3
from django import template
from django.utils.safestring import mark_safe

from apps.lessons.models import ALLOWED_ATTRIBUTES

register = template.Library()

@register.filter
def optimize_images(html, transform="c_limit,w_900,q_auto,f_auto"):
    pattern = r'(https://res\.cloudinary\.com/[^/]+/image/upload/)(?!c_|w_|q_|f_)'
    # Clean at render too: rows saved before Lesson.save sanitized, or written via update()/loaddata, skip it.
    html = nh3.clean(str(html), attributes=ALLOWED_ATTRIBUTES)
    return mark_safe(re.sub(pattern, rf'\1{transform}/', html))