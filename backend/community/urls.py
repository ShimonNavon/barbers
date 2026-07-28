from django.urls import path

from . import (views_dm, views_engage, views_feed, views_groups,
               views_members, views_reports)

app_name = "community"

urlpatterns = [
    path("", views_feed.feed, name="feed"),
    path("posts", views_feed.create_post, name="create_post"),
    path("posts/<int:post_id>/like", views_engage.toggle_like, name="like"),
    path("posts/<int:post_id>/comments", views_engage.comments,
         name="comments"),
    path("groups", views_groups.group_list, name="groups"),
    path("groups/<slug:slug>", views_groups.group_detail,
         name="group_detail"),
    path("groups/<slug:slug>/join", views_groups.join_toggle,
         name="group_join"),
    path("members", views_members.directory, name="members"),
    path("members/<int:member_id>", views_members.profile, name="profile"),
    path("me", views_members.me, name="me"),
    path("dm", views_dm.inbox, name="dm"),
    path("dm/badge", views_dm.badge, name="dm_badge"),
    path("dm/with/<int:member_id>", views_dm.open_with, name="dm_with"),
    path("dm/t/<int:conversation_id>", views_dm.thread, name="dm_thread"),
    path("dm/t/<int:conversation_id>/send", views_dm.send, name="dm_send"),
    path("dm/t/<int:conversation_id>/messages", views_dm.poll,
         name="dm_poll"),
    path("report", views_reports.report, name="report"),
]
