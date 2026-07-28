"""Regression tests for correctness defects found in review."""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from accounts.models import Member, OtpCode
from catalog.models import Barbershop
from community.models import Conversation, Message, Post
from community.tests.test_models import make_member


class LoginEdgeCaseTests(TestCase):
    def setUp(self):
        cache.clear()
        Barbershop.objects.create(owner_name="א", phone="0521111111",
                                  approved=True)
        Barbershop.objects.create(owner_name="ב", phone="0522222222",
                                  approved=True)

    def _login(self, local):
        self.client.post("/login", {"phone": local})
        code = OtpCode.objects.filter(used=False).latest("created_at").code
        return self.client.post("/login/verify", {"code": code})

    def test_switching_account_without_logout_does_not_crash(self):
        self._login("0521111111")
        r = self._login("0522222222")   # auth_login flushes the session
        self.assertEqual(r.status_code, 302)

    def test_approved_waitlist_client_cannot_enter_the_community(self):
        Barbershop.objects.create(
            owner_name="לקוחה", phone="0523333333", approved=True,
            applicant_type=Barbershop.ApplicantType.CLIENT)
        self.client.post("/login", {"phone": "0523333333"})
        # the community is for vetted professionals; "approved" on a waitlist
        # row means "handled", not "may join"
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_verify_is_rate_limited(self):
        self.client.post("/login", {"phone": "0521111111"})
        for _ in range(30):
            self.client.post("/login/verify", {"code": "000000"})
        code = OtpCode.objects.filter(used=False).first()
        self.assertIsNone(code, "code should be burned by the attempt cap")


class MalformedInputTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.client.force_login(self.member.user)

    def test_non_numeric_report_target_is_404_not_500(self):
        r = self.client.get("/report?post=abc")
        self.assertEqual(r.status_code, 404)

    def test_non_numeric_page_param_does_not_crash(self):
        r = self.client.get("/?page=abc")
        self.assertEqual(r.status_code, 200)

    def test_welcome_without_member_record_does_not_crash(self):
        staff = User.objects.create(username="staff-only", is_staff=True)
        self.client.force_login(staff)
        r = self.client.get("/welcome")
        self.assertIn(r.status_code, (302, 200))


class QueryCountTests(TestCase):
    """Query count must stay flat as rows grow — the defect these guard
    against is one extra query per post / per conversation."""

    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.client.force_login(self.member.user)

    def _queries_for(self, url):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        self.client.get(url)   # warm-up: the first hit also stamps last_seen
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url)
        return len(ctx)

    def test_feed_query_count_does_not_grow_with_posts(self):
        for i in range(3):
            author = make_member(phone=f"+97252000{i:04d}", name=f"מ{i}")
            Post.objects.create(author=author, text=f"פוסט {i}")
        few = self._queries_for("/")
        for i in range(3, 12):
            author = make_member(phone=f"+97252000{i:04d}", name=f"מ{i}")
            Post.objects.create(author=author, text=f"פוסט {i}")
        many = self._queries_for("/")
        self.assertEqual(few, many, "feed issues a query per post")

    def test_inbox_query_count_does_not_grow_with_conversations(self):
        def add_conversation(i):
            other = make_member(phone=f"+97253000{i:04d}", name=f"ח{i}")
            conv = Conversation.for_pair(self.member, other)
            Message.objects.create(conversation=conv, sender=other,
                                   text=f"הודעה {i}")
        for i in range(2):
            add_conversation(i)
        few = self._queries_for("/dm")
        for i in range(2, 10):
            add_conversation(i)
        many = self._queries_for("/dm")
        self.assertEqual(few, many, "inbox issues a query per conversation")


class PresenceTests(TestCase):
    def test_saving_profile_does_not_rewind_last_seen(self):
        cache.clear()   # last_seen is refreshed at most once per 5 min
        member = make_member()
        self.client.force_login(member.user)
        self.client.get("/")                      # stamps last_seen
        member.refresh_from_db()
        stamped = member.last_seen
        self.assertIsNotNone(stamped)
        self.client.post("/me", {"display_name": "שם חדש"})
        member.refresh_from_db()
        self.assertGreaterEqual(member.last_seen, stamped)
