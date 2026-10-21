from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(request, fallback):
    """The posted (or queried) "next" URL if it stays on this site, else fallback."""
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return fallback
