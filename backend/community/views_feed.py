from uuid import uuid4

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import redirect, render

from accounts.decorators import member_required
from accounts.images import process_upload
from accounts.throttle import allow

from .forms import PostForm
from .models import Group, GroupMembership, Like, Post

PAGE_SIZE = 20


def feed_queryset(member, group=None):
    qs = (Post.objects.filter(is_deleted=False)
          # author__application: every card renders occupation_display, which
          # walks Member -> Barbershop (one extra query per post otherwise)
          .select_related("author", "author__application", "group")
          .annotate(
              like_count=Count("likes", distinct=True),
              comment_count=Count("comments", distinct=True,
                                  filter=Q(comments__is_deleted=False)),
              liked=Exists(Like.objects.filter(
                  post=OuterRef("pk"), member=member)))
          # aggregation strips Meta.ordering — order explicitly
          .order_by("-created_at", "-pk"))
    if group is not None:
        qs = qs.filter(group=group)
    return qs


def _joined_groups(member):
    return [gm.group for gm in
            member.group_memberships.select_related("group")]


@member_required
def feed(request):
    page = Paginator(feed_queryset(request.member),
                     PAGE_SIZE).get_page(request.GET.get("page"))
    template = ("community/partials/post_list.html"
                if request.headers.get("HX-Request")
                else "community/feed.html")
    return render(request, template,
                  {"page": page, "joined_groups": _joined_groups(request.member),
                   "feed_url": "/"})


@member_required
def create_post(request):
    if request.method != "POST":
        return redirect("community:feed")
    form = PostForm(request.member, request.POST, request.FILES)

    def rerender():
        """Re-show the composer with the typed text intact, in the context it
        was written in (group page vs main feed) — losing a long post to a
        validation error is the worst possible outcome here."""
        slug = (request.POST.get("group") or "").strip()
        group = Group.objects.filter(slug=slug).first() if slug else None
        page = Paginator(feed_queryset(request.member, group=group),
                         PAGE_SIZE).get_page(1)
        context = {"page": page, "form": form,
                   "joined_groups": _joined_groups(request.member),
                   "text_value": request.POST.get("text", "")}
        if group is not None:
            context.update({
                "group": group, "feed_url": f"/groups/{group.slug}",
                "joined": GroupMembership.objects.filter(
                    group=group, member=request.member).exists()})
            return render(request, "community/group_detail.html", context)
        context["feed_url"] = "/"
        return render(request, "community/feed.html", context)

    if not form.is_valid():
        return rerender()
    if not allow(f"post:{request.member.pk}", 10, 3600):
        # a bare fragment would replace the whole page on this normal form
        # POST; bounce back with a flash instead
        messages.warning(request, "לאט לאט 🙂 נסו שוב בעוד כמה דקות.")
        return rerender()
    post = Post(author=request.member, text=form.cleaned_data["text"],
                group=form.cleaned_data.get("group"))
    upload = form.cleaned_data.get("image")
    if upload:
        try:
            content = process_upload(upload)
        except ValidationError as e:
            form.add_error("image", e.messages[0])
            return rerender()
        post.image.save(f"{uuid4().hex}.webp", content, save=False)
    post.save()
    dest = form.cleaned_data.get("group")
    # literal path: the group page route lands in a later task
    return redirect(f"/groups/{dest.slug}" if dest else "community:feed")
