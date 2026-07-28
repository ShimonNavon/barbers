from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from .models import Member


def _bounce(request, url):
    """Send the browser to `url`. For htmx requests a plain redirect would be
    followed by the XHR and the resulting full page swapped into whatever
    small element issued the request — so use HX-Redirect and an empty body."""
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


def member_required(view):
    """Community pages need a logged-in, onboarded member.
    Attaches `request.member` and refreshes `last_seen` (≤ once / 5 min)."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _bounce(request, "/login")
        member = getattr(request.user, "member", None)
        if member is None:
            return _bounce(request, "/login")
        if not member.onboarded:
            return _bounce(request, "/welcome")
        if cache.add(f"seen:{member.pk}", 1, 300):
            Member.objects.filter(pk=member.pk).update(
                last_seen=timezone.now())
        request.member = member
        return view(request, *args, **kwargs)
    return wrapped
