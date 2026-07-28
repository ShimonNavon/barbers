"""Regression tests for security defects found in review."""
import os
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.images import process_upload
from accounts.models import OtpCode
from accounts.views import client_ip
from catalog.models import Barbershop

MEDIA_TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class CertificateTraversalTests(TestCase):
    """Applicants' personal documents are staff-only. The gate must not be
    fooled by alternative spellings of the same path."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.makedirs(os.path.join(MEDIA_TMP, "certificates"), exist_ok=True)
        with open(os.path.join(MEDIA_TMP, "certificates", "c.pdf"), "wb") as f:
            f.write(b"personal document")

    def test_member_cannot_reach_certificates_by_any_spelling(self):
        self.client.force_login(User.objects.create(username="member"))
        for path in [
            "/media/certificates/c.pdf",
            "/media//certificates/c.pdf",
            "/media/./certificates/c.pdf",
            "/media/avatars/../certificates/c.pdf",
            "/media/%2e/certificates/c.pdf",
        ]:
            r = self.client.get(path)
            self.assertNotEqual(
                r.status_code, 200,
                f"{path} leaked a staff-only certificate to a member")

    def test_staff_still_reach_certificates(self):
        self.client.force_login(
            User.objects.create(username="boss", is_staff=True))
        r = self.client.get("/media/certificates/c.pdf")
        self.assertEqual(r.status_code, 200)


class ClientIpTrustTests(TestCase):
    """X-Forwarded-For is attacker-controlled: nginx appends to whatever the
    client sent, so index 0 is spoofable and must never key a rate limit."""

    def test_spoofed_forwarded_for_is_ignored(self):
        request = self.client.request().wsgi_request
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4, 127.0.0.1"
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        self.assertNotEqual(client_ip(request), "1.2.3.4")

    def test_cloudflare_header_is_used_when_present(self):
        request = self.client.request().wsgi_request
        request.META["HTTP_CF_CONNECTING_IP"] = "9.9.9.9"
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4"
        self.assertEqual(client_ip(request), "9.9.9.9")


@override_settings(MASTER_OTP_PAIRS={"+972500000001": "12345"})
class MasterCodeBruteForceTests(TestCase):
    """Per-IP limits alone are useless against rotated IPs; the phone in the
    session is the one identifier an attacker cannot rotate."""

    def setUp(self):
        cache.clear()
        Barbershop.objects.create(owner_name="בעלים", phone="0500000001",
                                  approved=True)

    def _attempt(self, code, ip):
        self.client.post("/login", {"phone": "0500000001"},
                         HTTP_CF_CONNECTING_IP=ip)
        return self.client.post("/login/verify", {"code": code},
                                HTTP_CF_CONNECTING_IP=ip)

    def test_rotating_ips_cannot_brute_force_the_master_code(self):
        for i in range(30):
            self._attempt("00000", f"5.5.{i}.{i}")
        r = self._attempt("12345", "8.8.8.8")  # the real code, fresh IP
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(r.status_code, 200)


class CertificateUploadTests(TestCase):
    """The public applicant endpoint stores files that staff later open from
    the admin origin — an .html/.svg there is stored XSS against the admin."""

    def _post(self, name, content, content_type):
        return self.client.post("/api/barbershops/", {
            "owner_name": "בודק", "phone": "0521234567",
            "certificate": SimpleUploadedFile(name, content, content_type),
        })

    def test_html_certificate_rejected(self):
        r = self._post("evil.html", b"<script>alert(1)</script>", "text/html")
        self.assertEqual(r.status_code, 400)

    def test_svg_certificate_rejected(self):
        r = self._post("evil.svg", b"<svg xmlns='http://www.w3.org/2000/svg'"
                                   b"><script>alert(1)</script></svg>",
                       "image/svg+xml")
        self.assertEqual(r.status_code, 400)

    def test_pdf_certificate_accepted(self):
        r = self._post("cert.pdf", b"%PDF-1.4 fake", "application/pdf")
        self.assertEqual(r.status_code, 201)


class DecompressionBombTests(TestCase):
    def test_pixel_bomb_rejected_not_oom(self):
        buf = BytesIO()
        # ~170M pixels but tiny on the wire — byte caps do not catch this
        Image.new("RGB", (13000, 13000), "white").save(buf, "PNG")
        upload = SimpleUploadedFile("bomb.png", buf.getvalue(), "image/png")
        self.assertLess(upload.size, 5 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            process_upload(upload)
