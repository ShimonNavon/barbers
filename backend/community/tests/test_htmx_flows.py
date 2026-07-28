"""Regression tests for htmx/partial-response defects found in review.

The common failure mode: an endpoint reached by hx-get returns a FULL page
(or a status htmx refuses to swap), so either a whole document gets injected
into a small element, or the user gets no feedback at all.
"""
from django.core.cache import cache
from django.test import TestCase

from community.models import Conversation, Message, Post
from community.tests.test_models import make_member

HX = {"HTTP_HX_REQUEST": "true"}


class ProfilePaginationTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.client.force_login(self.member.user)

    def test_profile_pagination_returns_partial_not_full_page(self):
        for i in range(25):
            Post.objects.create(author=self.member, text=f"פוסט {i}")
        r = self.client.get(f"/members/{self.member.pk}?page=2", **HX)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "<html")
        self.assertNotContains(r, "tabbar")


class TabbarGatingTests(TestCase):
    def test_onboarding_page_has_no_tabbar_or_badge_poller(self):
        member = make_member()
        member.onboarded = False
        member.save()
        self.client.force_login(member.user)
        r = self.client.get("/welcome")
        self.assertEqual(r.status_code, 200)
        # the badge poller would hit a member_required endpoint that bounces
        # back to this very page, injecting a whole nested copy of it
        self.assertNotContains(r, '/dm/badge')
        self.assertNotContains(r, "tabbar")


class HtmxAuthFailureTests(TestCase):
    def test_htmx_request_when_logged_out_does_not_return_full_page(self):
        r = self.client.get("/dm/badge", **HX)
        self.assertNotIn(r.status_code, (200,))
        self.assertNotContains(r, "<html", status_code=r.status_code)
        # htmx honours HX-Redirect for a real client-side navigation
        self.assertEqual(r.headers.get("HX-Redirect"), "/login")


class DmPollTests(TestCase):
    def setUp(self):
        cache.clear()
        self.dana = make_member()
        self.yossi = make_member(phone="+972529999999", name="יוסי")
        self.client.force_login(self.dana.user)
        self.conv = Conversation.for_pair(self.dana, self.yossi)

    def test_poll_with_no_new_messages_returns_204(self):
        m = Message.objects.create(conversation=self.conv, sender=self.yossi,
                                   text="שלום")
        r = self.client.get(f"/dm/t/{self.conv.pk}/messages?after={m.pk}")
        # 204 => htmx does not swap and after-swap never fires, so the thread
        # does not scroll-jump every 5s while reading history
        self.assertEqual(r.status_code, 204)

    def test_poll_with_new_messages_returns_content(self):
        Message.objects.create(conversation=self.conv, sender=self.yossi,
                               text="חדש")
        r = self.client.get(f"/dm/t/{self.conv.pk}/messages?after=0")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "חדש")


class ThrottleFeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)
        self.post = Post.objects.create(author=self.member, text="פוסט")

    def test_comment_throttle_is_swappable_and_visible(self):
        for i in range(30):
            self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": f"תגובה {i}"})
        r = self.client.post(f"/posts/{self.post.pk}/comments",
                             {"text": "אחת יותר מדי"}, **HX)
        # htmx refuses to swap 4xx, so feedback must ride a 2xx response
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "לאט לאט")

    def test_like_throttle_returns_intact_button(self):
        for _ in range(60):
            self.client.post(f"/posts/{self.post.pk}/like", **HX)
        r = self.client.post(f"/posts/{self.post.pk}/like", **HX)
        self.assertEqual(r.status_code, 200)
        # must still be a like button, not a banner that replaces it forever
        self.assertContains(r, "hx-post=")

    def test_post_throttle_returns_full_page_and_keeps_text(self):
        for i in range(10):
            self.client.post("/posts", {"text": f"פוסט {i}"})
        r = self.client.post("/posts", {"text": "אחד יותר מדי"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "<html")          # not a bare fragment
        self.assertContains(r, "לאט לאט")        # user is told why
        self.assertContains(r, "אחד יותר מדי")   # their text is not lost

    def test_report_throttle_tells_the_user(self):
        for i in range(10):
            self.client.post(f"/report?post={self.post.pk}",
                             {"reason": f"סיבה {i}"})
        r = self.client.post(f"/report?post={self.post.pk}",
                             {"reason": "עוד אחד"}, follow=True)
        self.assertContains(r, "לאט לאט")


class ComposerPreservesInputTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)

    def test_over_long_post_redisplays_text(self):
        long_text = "א" * 2001
        r = self.client.post("/posts", {"text": long_text})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "א" * 100)  # the text survived the round-trip
