import re

from django.conf import settings


def site_verification(request):
    """Google Search Console ownership token for the <meta> tag in base.html (blank: no tag).

    Accepts the bare token or the whole tag Search Console shows, since both get pasted into the setting.
    """
    value = settings.GOOGLE_SITE_VERIFICATION.strip()
    pasted_tag = re.search(r'content\s*=\s*["\']([^"\']+)["\']', value)
    return {"google_site_verification": pasted_tag.group(1) if pasted_tag else value}
