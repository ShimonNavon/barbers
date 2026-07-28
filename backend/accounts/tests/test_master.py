from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import Member, OtpCode
from catalog.models import Barbershop

MASTER = {"MASTER_OTP_PHONE": "+972500000001",
          "MASTER_OTP_CODE": "1234567890"}


def make_app(phone="0500000001", name="סימון"):
    return Barbershop.objects.create(owner_name=name, phone=phone,
                                     approved=True)


@override_settings(**MASTER)
class MasterOtpTests(TestCase):
    def setUp(self):
        cache.clear()
        make_app()
        self.client.post("/login", {"phone": "0500000001"})

    def test_master_code_logs_in_without_issued_otp(self):
        OtpCode.objects.all().delete()
        r = self.client.post("/login/verify", {"code": "1234567890"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_master_code_reusable_across_logins(self):
        self.client.post("/login/verify", {"code": "1234567890"})
        self.client.post("/logout")
        self.client.post("/login", {"phone": "0500000001"})
        r = self.client.post("/login/verify", {"code": "1234567890"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Member.objects.count(), 1)

    def test_master_code_rejected_for_other_phone(self):
        make_app(phone="0521234567", name="אחר")
        c = self.client_class()
        c.post("/login", {"phone": "0521234567"})
        r = c.post("/login/verify", {"code": "1234567890"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", c.session)

    def test_wrong_master_code_fails(self):
        OtpCode.objects.all().delete()
        self.client.post("/login/verify", {"code": "9999999999"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_master_brute_force_throttled_per_ip(self):
        OtpCode.objects.all().delete()
        for _ in range(10):
            self.client.post("/login/verify", {"code": "0000000000"})
        self.client.post("/login/verify", {"code": "1234567890"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_disabled_when_unconfigured(self):
        with self.settings(MASTER_OTP_CODE=""):
            OtpCode.objects.all().delete()
            self.client.post("/login/verify", {"code": "1234567890"})
            self.assertNotIn("_auth_user_id", self.client.session)
