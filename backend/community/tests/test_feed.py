from django.core.cache import cache
from django.test import TestCase

from community.models import Group, GroupMembership, Post
from community.tests.test_models import make_member


class FeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r["Location"])

    def test_not_onboarded_redirected_to_welcome(self):
        self.member.onboarded = False
        self.member.save()
        r = self.client.get("/")
        self.assertRedirects(r, "/welcome")

    def test_feed_shows_all_posts_with_group_chip(self):
        g = Group.objects.create(name="ברברים", slug="barbers")
        other = make_member(phone="+972529999999", name="יוסי")
        Post.objects.create(author=other, text="פוסט ראשי")
        Post.objects.create(author=other, group=g, text="פוסט קבוצתי")
        r = self.client.get("/")
        self.assertContains(r, "פוסט ראשי")
        self.assertContains(r, "פוסט קבוצתי")
        self.assertContains(r, "ברברים")  # the chip

    def test_deleted_posts_hidden(self):
        Post.objects.create(author=self.member, text="נמחק", is_deleted=True)
        r = self.client.get("/")
        self.assertNotContains(r, "נמחק")

    def test_create_post_main_feed(self):
        r = self.client.post("/posts", {"text": "שלום לכולם"})
        self.assertRedirects(r, "/")
        self.assertEqual(Post.objects.count(), 1)

    def test_create_post_text_bound(self):
        r = self.client.post("/posts", {"text": "א" * 2001})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)

    def test_post_to_group_requires_membership(self):
        g = Group.objects.create(name="ברברים", slug="barbers")
        r = self.client.post("/posts", {"text": "היי", "group": "barbers"})
        self.assertEqual(Post.objects.count(), 0)
        GroupMembership.objects.create(group=g, member=self.member)
        self.client.post("/posts", {"text": "היי", "group": "barbers"})
        self.assertEqual(Post.objects.get().group, g)

    def test_post_rate_limited_at_ten_per_hour(self):
        for i in range(11):
            self.client.post("/posts", {"text": f"פוסט {i}"})
        self.assertEqual(Post.objects.count(), 10)

    def test_pagination_htmx_partial(self):
        for i in range(25):
            Post.objects.create(author=self.member, text=f"פוסט מספר {i}")
        r = self.client.get("/?page=2", HTTP_HX_REQUEST="true")
        self.assertContains(r, "פוסט מספר 4")   # oldest land on page 2
        self.assertNotContains(r, "<nav")        # partial, not full page
