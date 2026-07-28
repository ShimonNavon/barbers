from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import Member, OtpCode
from catalog.models import Barbershop

PAIRS = {"+972500000001": "12345", "+972529999999": "9876543210"}


def make_app(phone="0500000001", name="סימון"):
    return Barbershop.objects.create(owner_name=name, phone=phone,
                                     approved=True)


@override_settings(MASTER_OTP_PAIRS=PAIRS)
class MasterOtpTests(TestCase):
    def setUp(self):
        cache.clear()
        make_app()
        self.client.post("/login", {"phone": "0500000001"})

    def test_master_code_logs_in_without_issued_otp(self):
        OtpCode.objects.all().delete()
        r = self.client.post("/login/verify", {"code": "12345"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_master_code_reusable_across_logins(self):
        self.client.post("/login/verify", {"code": "12345"})
        self.client.post("/logout")
        self.client.post("/login", {"phone": "0500000001"})
        r = self.client.post("/login/verify", {"code": "12345"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Member.objects.count(), 1)

    def test_second_pair_has_its_own_code(self):
        make_app(phone="0529999999", name="לקוחה")
        c = self.client_class()
        c.post("/login", {"phone": "0529999999"})
        # the other pair's code does not work for this phone
        c.post("/login/verify", {"code": "12345"})
        self.assertNotIn("_auth_user_id", c.session)
        r = c.post("/login/verify", {"code": "9876543210"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("_auth_user_id", c.session)

    def test_master_code_rejected_for_unlisted_phone(self):
        make_app(phone="0521234567", name="אחר")
        c = self.client_class()
        c.post("/login", {"phone": "0521234567"})
        r = c.post("/login/verify", {"code": "12345"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)

    def test_wrong_master_code_fails(self):
        OtpCode.objects.all().delete()
        self.client.post("/login/verify", {"code": "99999"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_master_brute_force_throttled_per_ip(self):
        OtpCode.objects.all().delete()
        for _ in range(10):
            self.client.post("/login/verify", {"code": "00000"})
        self.client.post("/login/verify", {"code": "12345"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_disabled_when_unconfigured(self):
        with self.settings(MASTER_OTP_PAIRS={}):
            OtpCode.objects.all().delete()
            self.client.post("/login/verify", {"code": "12345"})
            self.assertNotIn("_auth_user_id", self.client.session)
