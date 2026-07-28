from functools import wraps

from django.core.cache import cache
from django.shortcuts import redirect
from django.utils import timezone

from .models import Member


def member_required(view):
    """Community pages need a logged-in, onboarded member.
    Attaches `request.member` and refreshes `last_seen` (≤ once / 5 min)."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        member = getattr(request.user, "member", None)
        if member is None:
            return redirect("accounts:login")
        if not member.onboarded:
            return redirect("accounts:onboarding")
        if cache.add(f"seen:{member.pk}", 1, 300):
            Member.objects.filter(pk=member.pk).update(
                last_seen=timezone.now())
        request.member = member
        return view(request, *args, **kwargs)
    return wrapped
