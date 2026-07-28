from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from accounts.images import MAX_BYTES, process_upload


def png_upload(width=10, height=10, name="t.png"):
    buf = BytesIO()
    Image.new("RGB", (width, height), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), "image/png")


class ProcessUploadTests(SimpleTestCase):
    def test_valid_png_reencoded_to_webp(self):
        content = process_upload(png_upload())
        self.assertEqual(Image.open(BytesIO(content.read())).format, "WEBP")

    def test_oversize_bytes_rejected(self):
        f = SimpleUploadedFile("big.png", b"x" * (MAX_BYTES + 1), "image/png")
        with self.assertRaises(ValidationError):
            process_upload(f)

    def test_non_image_rejected(self):
        f = SimpleUploadedFile("evil.png", b"MZ not an image", "image/png")
        with self.assertRaises(ValidationError):
            process_upload(f)

    def test_unsupported_format_rejected(self):
        buf = BytesIO()
        Image.new("RGB", (5, 5)).save(buf, "BMP")
        f = SimpleUploadedFile("t.bmp", buf.getvalue(), "image/bmp")
        with self.assertRaises(ValidationError):
            process_upload(f)

    def test_large_dimensions_resized(self):
        content = process_upload(png_upload(width=4000, height=1000))
        img = Image.open(BytesIO(content.read()))
        self.assertLessEqual(max(img.size), 1600)
