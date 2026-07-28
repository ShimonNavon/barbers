from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required
from accounts.throttle import allow

from .models import Comment, Post, Report


class ReportForm(forms.Form):
    reason = forms.CharField(max_length=500)


def _target(request):
    def as_id(raw):
        # a non-numeric pk reaches the DB layer as ValueError -> 500
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise Http404

    post_id = request.GET.get("post")
    comment_id = request.GET.get("comment")
    if post_id:
        return {"post": get_object_or_404(Post, pk=as_id(post_id))}
    if comment_id:
        return {"comment": get_object_or_404(Comment, pk=as_id(comment_id))}
    raise Http404


@member_required
def report(request):
    target = _target(request)
    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if allow(f"report:{request.member.pk}", 10, 3600):
            Report.objects.create(reporter=request.member,
                                  reason=form.cleaned_data["reason"], **target)
            messages.success(request, "תודה, הדיווח התקבל ויטופל.")
        else:
            # silently dropping a report looked identical to accepting one
            messages.warning(request, "לאט לאט 🙂 נסו שוב בעוד כמה דקות.")
        return redirect("community:feed")
    return render(request, "community/report.html",
                  {"form": form, "qs": request.META.get("QUERY_STRING", "")})
