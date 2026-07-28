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
