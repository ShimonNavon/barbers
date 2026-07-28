from django.shortcuts import get_object_or_404, render

from accounts.decorators import member_required
from accounts.throttle import allow

from .forms import CommentForm
from .models import Like, Post
from .views_feed import feed_queryset


def _post_for(member, post_id):
    return get_object_or_404(feed_queryset(member), pk=post_id)


@member_required
def toggle_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    if request.method == "POST" and allow(f"like:{request.member.pk}",
                                          60, 3600):
        existing = Like.objects.filter(post=post, member=request.member)
        if existing.exists():
            existing.delete()
        else:
            Like.objects.get_or_create(post=post, member=request.member)
    # Always re-render the button itself: htmx swaps it outerHTML, so any
    # other body (banner, error page) would destroy the control permanently.
    return render(request, "community/partials/like_button.html",
                  {"post": _post_for(request.member, post_id)})


@member_required
def comments(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    form = CommentForm()
    throttled = False
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            if allow(f"comment:{request.member.pk}", 30, 3600):
                post.comments.create(author=request.member,
                                     text=form.cleaned_data["text"])
                form = CommentForm()
            else:
                throttled = True
    visible = post.comments.filter(is_deleted=False).select_related("author")
    # 200, not 429: htmx never swaps 4xx, so a 429 would make the limit
    # invisible — the comment would just vanish with no explanation.
    return render(request, "community/partials/comment_list.html",
                  {"post": post, "comments": visible, "form": form,
                   "throttled": throttled})
