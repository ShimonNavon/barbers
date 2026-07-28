from django.core.cache import cache
from django.test import TestCase

from community.models import Comment, Like, Post
from community.tests.test_models import make_member


class LikeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.post = Post.objects.create(author=self.member, text="פוסט")

    def test_like_then_unlike(self):
        r = self.client.post(f"/posts/{self.post.pk}/like")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Like.objects.count(), 1)
        self.assertContains(r, "♥ 1")
        r = self.client.post(f"/posts/{self.post.pk}/like")
        self.assertEqual(Like.objects.count(), 0)
        self.assertContains(r, "♥ 0")

    def test_like_deleted_post_404(self):
        self.post.is_deleted = True
        self.post.save()
        r = self.client.post(f"/posts/{self.post.pk}/like")
        self.assertEqual(r.status_code, 404)


class CommentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.post = Post.objects.create(author=self.member, text="פוסט")

    def test_comment_create_and_list(self):
        r = self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": "מהמם!"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "מהמם!")
        self.assertEqual(Comment.objects.count(), 1)

    def test_comment_bound_500(self):
        self.client.post(f"/posts/{self.post.pk}/comments",
                         {"text": "א" * 501})
        self.assertEqual(Comment.objects.count(), 0)

    def test_deleted_comments_hidden(self):
        Comment.objects.create(post=self.post, author=self.member,
                               text="הוסר", is_deleted=True)
        r = self.client.get(f"/posts/{self.post.pk}/comments")
        self.assertNotContains(r, "הוסר")

    def test_comment_rate_limit_thirty_per_hour(self):
        for i in range(31):
            self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": f"תגובה {i}"})
        self.assertEqual(Comment.objects.count(), 30)
