from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import member_required
from accounts.images import process_upload
from accounts.models import Member
from catalog.models import Barbershop

from .views_feed import PAGE_SIZE, feed_queryset


class ProfileForm(forms.Form):
    display_name = forms.CharField(max_length=50)
    bio = forms.CharField(max_length=300, required=False)
    avatar = forms.FileField(required=False)


@member_required
def directory(request):
    members = (Member.objects.filter(onboarded=True)
               .select_related("application").order_by("display_name"))
    q = request.GET.get("q", "").strip()[:50]
    occupation = request.GET.get("occupation", "").strip()[:20]
    city = request.GET.get("city", "").strip()[:100]
    if q:
        members = members.filter(display_name__icontains=q)
    if occupation:
        members = members.filter(application__occupation=occupation)
    if city:
        members = members.filter(application__city__icontains=city)
    return render(request, "community/members.html", {
        "members": members[:200],
        "occupations": Barbershop.Occupation.choices,
        "q": q, "occupation": occupation, "city": city,
    })


@member_required
def profile(request, member_id):
    person = get_object_or_404(
        Member.objects.select_related("application"),
        pk=member_id, onboarded=True)
    page = (Paginator(feed_queryset(request.member).filter(author=person),
                      PAGE_SIZE).get_page(request.GET.get("page")))
    return render(request, "community/profile.html",
                  {"person": person, "page": page,
                   "feed_url": f"/members/{member_id}"})


@member_required
def me(request):
    member = request.member
    form = ProfileForm(request.POST or None, request.FILES or None,
                       initial={"display_name": member.display_name,
                                "bio": member.bio})
    if request.method == "POST" and form.is_valid():
        member.display_name = form.cleaned_data["display_name"]
        member.bio = form.cleaned_data.get("bio", "")
        avatar = form.cleaned_data.get("avatar")
        if avatar:
            try:
                content = process_upload(avatar)
                member.avatar.save(f"{uuid4().hex}.webp", content, save=False)
            except ValidationError as e:
                form.add_error("avatar", e.messages[0])
                return render(request, "community/profile_edit.html",
                              {"form": form, "member": member})
        member.save()
        return redirect("community:me")
    return render(request, "community/profile_edit.html",
                  {"form": form, "member": member})
