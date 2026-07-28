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


class Conversation(models.Model):
    # pk-ordered pair → exactly one row per pair of members
    member_low = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                                   related_name="+")
    member_high = models.ForeignKey("accounts.Member",
                                    on_delete=models.CASCADE,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["member_low", "member_high"],
            name="uniq_conversation_pair")]

    @classmethod
    def for_pair(cls, a, b):
        lo, hi = sorted((a, b), key=lambda m: m.pk)
        conv, _ = cls.objects.get_or_create(member_low=lo, member_high=hi)
        return conv

    def involves(self, member):
        return member.pk in (self.member_low_id, self.member_high_id)

    def other(self, member):
        if member.pk == self.member_low_id:
            return self.member_high
        return self.member_low


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                     related_name="messages")
    sender = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,
                               related_name="sent_messages")
    text = models.CharField(max_length=2000)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
