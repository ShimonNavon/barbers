from django.urls import path

from . import views_engage, views_feed, views_groups, views_members

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
]
