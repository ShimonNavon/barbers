from django.db import models


class Group(models.Model):
    name = models.CharField("שם", max_length=60, unique=True)
    slug = models.SlugField(unique=True, allow_unicode=True)
    emoji = models.CharField("אימוג'י", max_length=8, blank=True, default="")
    description = models.CharField("תיאור", max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "קבוצה"
        verbose_name_plural = "קבוצות"

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE,
                              related_name="memberships")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="group_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["group", "member"], name="uniq_group_member")]


class Post(models.Model):
    author = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="posts")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name="posts")
    text = models.CharField("טקסט", max_length=2000)
    image = models.ImageField(upload_to="posts/", blank=True, null=True)
    is_deleted = models.BooleanField("הוסר", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # -pk tiebreaks same-instant rows (bulk seeds, fast posting)
        ordering = ["-created_at", "-pk"]
        verbose_name = "פוסט"
        verbose_name_plural = "פוסטים"

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE,
                             related_name="comments")
    author = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="comments")
    text = models.CharField("תגובה", max_length=500)
    is_deleted = models.BooleanField("הוסר", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "תגובה"
        verbose_name_plural = "תגובות"


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE,
                             related_name="likes")
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["post", "member"], name="uniq_like_post_member")]
