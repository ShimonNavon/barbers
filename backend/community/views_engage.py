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
    if request.method != "POST":
        return render(request, "community/partials/throttled.html", status=405)
    if not allow(f"like:{request.member.pk}", 60, 3600):
        return render(request, "community/partials/throttled.html", status=429)
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    existing = Like.objects.filter(post=post, member=request.member)
    if existing.exists():
        existing.delete()
    else:
        Like.objects.get_or_create(post=post, member=request.member)
    return render(request, "community/partials/like_button.html",
                  {"post": _post_for(request.member, post_id)})


@member_required
def comments(request, post_id):
    post = get_object_or_404(Post, pk=post_id, is_deleted=False)
    form = CommentForm()
    status = 200
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            if allow(f"comment:{request.member.pk}", 30, 3600):
                post.comments.create(author=request.member,
                                     text=form.cleaned_data["text"])
                form = CommentForm()
            else:
                status = 429
    visible = post.comments.filter(is_deleted=False).select_related("author")
    return render(request, "community/partials/comment_list.html",
                  {"post": post, "comments": visible, "form": form,
                   "throttled": status == 429},
                  status=status)
