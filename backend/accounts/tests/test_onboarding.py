import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import Member
from catalog.models import Barbershop

MEDIA_TMP = tempfile.mkdtemp()


def login_member(client, phone="+972521234567", onboarded=False):
    app = Barbershop.objects.create(owner_name="דנה כהן", phone="0521234567",
                                    approved=True)
    user = User.objects.create(username=phone)
    member = Member.objects.create(user=user, application=app,
                                   display_name="דנה כהן", phone_e164=phone,
                                   onboarded=onboarded)
    client.force_login(user)
    return member


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class OnboardingTests(TestCase):
    def test_requires_login(self):
        r = self.client.get("/welcome")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r["Location"])

    def test_get_prefills_display_name(self):
        login_member(self.client)
        r = self.client.get("/welcome")
        self.assertContains(r, "דנה כהן")

    def test_post_saves_and_marks_onboarded(self):
        m = login_member(self.client)
        r = self.client.post("/welcome", {"display_name": "דנה ✂️"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        m.refresh_from_db()
        self.assertTrue(m.onboarded)
        self.assertEqual(m.display_name, "דנה ✂️")

    def test_avatar_upload_saved_as_webp(self):
        m = login_member(self.client)
        buf = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(buf, "JPEG")
        avatar = SimpleUploadedFile("me.jpg", buf.getvalue(), "image/jpeg")
        self.client.post("/welcome", {"display_name": "דנה", "avatar": avatar})
        m.refresh_from_db()
        self.assertTrue(m.avatar.name.endswith(".webp"))

    def test_display_name_bounded_at_50(self):
        login_member(self.client)
        r = self.client.post("/welcome", {"display_name": "א" * 51})
        self.assertEqual(r.status_code, 200)  # re-rendered with error
