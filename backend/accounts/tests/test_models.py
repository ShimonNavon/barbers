from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Member, OtpCode
from catalog.models import Barbershop


def make_application(**kw):
    defaults = dict(
        owner_name="דנה כהן", phone="0521234567", city="חיפה",
        occupation=Barbershop.Occupation.HAIR, approved=True,
    )
    defaults.update(kw)
    return Barbershop.objects.create(**defaults)


class MemberTests(TestCase):
    def test_member_reads_profile_fields_through_application(self):
        app = make_application(instagram="dana.hair")
        user = User.objects.create(username="+972521234567")
        m = Member.objects.create(
            user=user, application=app,
            display_name="דנה", phone_e164="+972521234567",
        )
        self.assertEqual(m.city, "חיפה")
        self.assertEqual(m.instagram, "dana.hair")
        self.assertEqual(m.occupation_display, "מעצב/ת שיער")

    def test_phone_unique(self):
        app1, app2 = make_application(), make_application(phone="0529999999")
        u1 = User.objects.create(username="a")
        u2 = User.objects.create(username="b")
        Member.objects.create(user=u1, application=app1,
                              display_name="א", phone_e164="+972521234567")
        with self.assertRaises(Exception):
            Member.objects.create(user=u2, application=app2,
                                  display_name="ב", phone_e164="+972521234567")


class OtpCodeTests(TestCase):
    def test_issue_creates_six_digit_code_with_ttl(self):
        otp = OtpCode.issue("+972521234567")
        self.assertRegex(otp.code, r"^\d{6}$")
        self.assertFalse(otp.used)
        self.assertTrue(otp.expires_at > timezone.now())

    def test_issue_invalidates_previous_codes(self):
        first = OtpCode.issue("+972521234567")
        OtpCode.issue("+972521234567")
        first.refresh_from_db()
        self.assertTrue(first.used)

    def test_check_code_happy_path_is_single_use(self):
        otp = OtpCode.issue("+972521234567")
        self.assertTrue(OtpCode.check_code("+972521234567", otp.code))
        self.assertFalse(OtpCode.check_code("+972521234567", otp.code))

    def test_wrong_code_counts_attempts_and_caps_at_five(self):
        otp = OtpCode.issue("+972521234567")
        for _ in range(5):
            self.assertFalse(OtpCode.check_code("+972521234567", "000000"))
        # even the right code fails after the cap
        self.assertFalse(OtpCode.check_code("+972521234567", otp.code))

    def test_expired_code_fails(self):
        otp = OtpCode.issue("+972521234567")
        OtpCode.objects.filter(pk=otp.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(OtpCode.check_code("+972521234567", otp.code))
