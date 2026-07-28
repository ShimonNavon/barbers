from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required

from .models import Group, GroupMembership
from .views_feed import PAGE_SIZE, feed_queryset


@member_required
def group_list(request):
    groups = (Group.objects
              .annotate(member_count=Count("memberships"),
                        joined=Exists(GroupMembership.objects.filter(
                            group=OuterRef("pk"), member=request.member))))
    return render(request, "community/group_list.html", {"groups": groups})


@member_required
def join_toggle(request, slug):
    if request.method == "POST":
        group = get_object_or_404(Group, slug=slug)
        existing = GroupMembership.objects.filter(group=group,
                                                  member=request.member)
        if existing.exists():
            existing.delete()
        else:
            GroupMembership.objects.get_or_create(group=group,
                                                  member=request.member)
    return redirect("community:group_detail", slug=slug)


@member_required
def group_detail(request, slug):
    group = get_object_or_404(Group, slug=slug)
    joined = GroupMembership.objects.filter(
        group=group, member=request.member).exists()
    page = Paginator(feed_queryset(request.member, group=group),
                     PAGE_SIZE).get_page(request.GET.get("page"))
    if request.headers.get("HX-Request"):
        return render(request, "community/partials/post_list.html",
                      {"page": page, "feed_url": f"/groups/{slug}"})
    return render(request, "community/group_detail.html",
                  {"group": group, "joined": joined, "page": page,
                   "feed_url": f"/groups/{slug}"})
