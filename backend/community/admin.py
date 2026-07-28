from django.contrib import admin

from .models import Comment, Group, Post


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "emoji", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("author", "text", "group", "created_at", "is_deleted")
    list_filter = ("is_deleted", "group", "created_at")
    list_editable = ("is_deleted",)
    search_fields = ("text", "author__display_name")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "text", "post", "created_at", "is_deleted")
    list_filter = ("is_deleted", "created_at")
    list_editable = ("is_deleted",)
    search_fields = ("text", "author__display_name")
