from django import forms
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import member_required
from accounts.models import Member
from accounts.throttle import allow

from .models import Conversation, Message


class MessageForm(forms.Form):
    text = forms.CharField(max_length=2000)


def _own_conversation(request, conversation_id):
    conv = get_object_or_404(Conversation, pk=conversation_id)
    if not conv.involves(request.member):
        raise Http404
    return conv


def _mark_read(conv, member):
    (conv.messages.filter(read_at__isnull=True)
     .exclude(sender=member).update(read_at=timezone.now()))


@member_required
def open_with(request, member_id):
    if member_id == request.member.pk:
        raise Http404
    other = get_object_or_404(Member, pk=member_id, onboarded=True)
    conv = Conversation.for_pair(request.member, other)
    return redirect("community:dm_thread", conversation_id=conv.pk)


@member_required
def thread(request, conversation_id):
    conv = _own_conversation(request, conversation_id)
    _mark_read(conv, request.member)
    msgs = conv.messages.select_related("sender")
    last = msgs.last()
    return render(request, "community/dm_thread.html",
                  {"conv": conv, "msgs": msgs,
                   "other": conv.other(request.member),
                   "last_id": last.pk if last else 0})


@member_required
def send(request, conversation_id):
    conv = _own_conversation(request, conversation_id)
    if request.method != "POST":
        return redirect("community:dm_thread", conversation_id=conv.pk)
    form = MessageForm(request.POST)
    if form.is_valid() and allow(f"dm:{request.member.pk}", 60, 3600):
        Message.objects.create(conversation=conv, sender=request.member,
                               text=form.cleaned_data["text"])
    return redirect("community:dm_thread", conversation_id=conv.pk)


@member_required
def poll(request, conversation_id):
    conv = _own_conversation(request, conversation_id)
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    newer = conv.messages.filter(pk__gt=after).select_related("sender")
    _mark_read(conv, request.member)
    if not newer.exists():
        # 204 => htmx skips the swap, so after-swap never fires and the
        # thread stops yanking the reader back to the bottom every 5s
        return HttpResponse(status=204)
    return render(request, "community/partials/messages_page.html",
                  {"msgs": newer, "me": request.member})


@member_required
def inbox(request):
    me = request.member
    convs = (Conversation.objects
             .filter(Q(member_low=me) | Q(member_high=me))
             .select_related("member_low", "member_high")
             .annotate(last_at=Max("messages__created_at"),
                       unread=Count("messages", filter=Q(
                           messages__read_at__isnull=True)
                           & ~Q(messages__sender=me)))
             .exclude(last_at=None)
             .order_by("-last_at"))
    items = [{"conv": c, "other": c.other(me),
              "last": c.messages.last(), "unread": c.unread}
             for c in convs]
    return render(request, "community/dm_list.html", {"items": items})


@member_required
def badge(request):
    me = request.member
    total = (Message.objects
             .filter(Q(conversation__member_low=me)
                     | Q(conversation__member_high=me),
                     read_at__isnull=True)
             .exclude(sender=me).count())
    return render(request, "community/partials/dm_badge.html",
                  {"total": total})
