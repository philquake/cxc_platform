import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def optimize_images(html, transform="c_limit,w_900,q_auto,f_auto"):
    pattern = r'(https://res\.cloudinary\.com/[^/]+/image/upload/)(?!c_|w_|q_|f_)'
    # Lesson.save sanitizes (migration 0004 cleaned older rows), so this only adds the image transforms.
    return mark_safe(re.sub(pattern, rf'\1{transform}/', str(html)))
