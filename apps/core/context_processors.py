from django.conf import settings


def site_verification(request):
    """Google Search Console ownership token for the <meta> tag in base.html (blank: no tag)."""
    return {"google_site_verification": settings.GOOGLE_SITE_VERIFICATION}
