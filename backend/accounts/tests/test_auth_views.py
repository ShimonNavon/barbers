from django.core.cache import cache
from django.test import TestCase

from accounts.models import OtpCode
from catalog.models import Barbershop

GENERIC = "אם המספר רשום בקהילה"


def make_application(**kw):
    defaults = dict(owner_name="דנה כהן", phone="0521234567", approved=True)
    defaults.update(kw)
    return Barbershop.objects.create(**defaults)


class OtpRequestTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_login_page_renders(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "טלפון")

    def test_approved_phone_gets_code_and_generic_message(self):
        make_application()
        r = self.client.post("/login", {"phone": "052-123-4567"}, follow=True)
        self.assertContains(r, GENERIC)
        self.assertEqual(OtpCode.objects.count(), 1)
        self.assertEqual(OtpCode.objects.get().phone_e164, "+972521234567")

    def test_unknown_phone_same_message_no_code(self):
        r = self.client.post("/login", {"phone": "0529999999"}, follow=True)
        self.assertContains(r, GENERIC)
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_unapproved_application_no_code(self):
        make_application(approved=False)
        r = self.client.post("/login", {"phone": "0521234567"}, follow=True)
        self.assertContains(r, GENERIC)
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_invalid_format_shows_field_error(self):
        r = self.client.post("/login", {"phone": "abc"})
        self.assertContains(r, "מספר טלפון לא תקין")
        self.assertEqual(OtpCode.objects.count(), 0)

    def test_phone_throttle_three_per_window(self):
        make_application()
        for _ in range(4):
            self.client.post("/login", {"phone": "0521234567"}, follow=True)
        self.assertEqual(OtpCode.objects.count(), 3)

    def test_ip_throttle_ten_per_hour(self):
        # 10 distinct unknown phones exhaust the IP budget; approved #11 gets nothing
        make_application(phone="0521111111")
        for i in range(10):
            self.client.post("/login", {"phone": f"05299{i:05d}"}, follow=True)
        self.client.post("/login", {"phone": "0521111111"}, follow=True)
        self.assertEqual(OtpCode.objects.count(), 0)


from django.contrib.auth.models import User  # noqa: E402

from accounts.models import Member  # noqa: E402


class OtpVerifyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.app = make_application()
        self.client.post("/login", {"phone": "0521234567"})
        self.code = OtpCode.objects.get().code

    def test_correct_code_logs_in_creates_member_redirects_onboarding(self):
        r = self.client.post("/login/verify", {"code": self.code})
        self.assertRedirects(r, "/welcome", fetch_redirect_response=False)
        m = Member.objects.get()
        self.assertEqual(m.phone_e164, "+972521234567")
        self.assertEqual(m.display_name, "דנה כהן")
        self.assertEqual(m.application, self.app)
        self.assertEqual(int(self.client.session["_auth_user_id"]), m.user.pk)

    def test_onboarded_member_redirects_to_feed(self):
        self.client.post("/login/verify", {"code": self.code})
        Member.objects.update(onboarded=True)
        self.client.post("/logout")
        self.client.post("/login", {"phone": "0521234567"})
        code2 = OtpCode.objects.filter(used=False).get().code
        r = self.client.post("/login/verify", {"code": code2})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertEqual(Member.objects.count(), 1)  # no duplicate

    def test_wrong_code_stays_anonymous(self):
        r = self.client.post("/login/verify", {"code": "000000"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "קוד שגוי")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verify_without_session_phone_redirects_login(self):
        c = self.client_class()
        r = c.post("/login/verify", {"code": "123456"})
        self.assertRedirects(r, "/login")

    def test_logout(self):
        self.client.post("/login/verify", {"code": self.code})
        self.client.post("/logout")
        self.assertNotIn("_auth_user_id", self.client.session)
