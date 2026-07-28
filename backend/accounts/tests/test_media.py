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


class WebpMimeTests(TestCase):
    def test_webp_mapping_ensured_even_on_bare_pythons(self):
        # python:3.12-slim ships no .webp mapping; serve() then sends
        # application/octet-stream which nosniff-blocks every image
        import mimetypes
        mimetypes.types_map.pop(".webp", None)
        from accounts.apps import ensure_mime_types
        ensure_mime_types()
        self.assertEqual(mimetypes.guess_type("a.webp")[0], "image/webp")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class MediaCacheControlTests(TestCase):
    def test_media_responses_forbid_edge_caching(self):
        # Cloudflare edge-caches image extensions by default; without
        # no-store, authenticated media becomes publicly cached (auth bypass)
        os.makedirs(os.path.join(MEDIA_TMP, "avatars"), exist_ok=True)
        with open(os.path.join(MEDIA_TMP, "avatars", "b.webp"), "wb") as f:
            f.write(b"data")
        self.client.force_login(User.objects.create(username="u2"))
        r = self.client.get("/media/avatars/b.webp")
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-store", r.get("Cache-Control", ""))
