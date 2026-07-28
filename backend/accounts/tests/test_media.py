import os
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

MEDIA_TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class MediaAuthTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(os.path.join(MEDIA_TMP, "certificates"), exist_ok=True)
        os.makedirs(os.path.join(MEDIA_TMP, "avatars"), exist_ok=True)
        for p in ("certificates/c.pdf", "avatars/a.webp"):
            with open(os.path.join(MEDIA_TMP, p), "wb") as f:
                f.write(b"data")

    def test_anonymous_gets_redirect(self):
        r = self.client.get("/media/avatars/a.webp")
        self.assertEqual(r.status_code, 302)

    def test_member_can_fetch_community_media(self):
        self.client.force_login(User.objects.create(username="u"))
        r = self.client.get("/media/avatars/a.webp")
        self.assertEqual(r.status_code, 200)

    def test_member_cannot_fetch_certificates(self):
        self.client.force_login(User.objects.create(username="u"))
        r = self.client.get("/media/certificates/c.pdf")
        self.assertEqual(r.status_code, 302)  # bounced to admin login

    def test_staff_can_fetch_certificates(self):
        self.client.force_login(
            User.objects.create(username="s", is_staff=True))
        r = self.client.get("/media/certificates/c.pdf")
        self.assertEqual(r.status_code, 200)
