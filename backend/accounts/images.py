from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1600
# A 500KB PNG can decode to gigabytes of RAM, so bytes alone are no defence.
# 50MP is far above any phone camera and ~200MB decoded worst case.
MAX_PIXELS = 50_000_000
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def save_image_field(field, content):
    """Attach re-encoded image `content` to `field`, deleting whatever file
    it held before. Without this every photo change leaks a file forever."""
    from uuid import uuid4
    old_name = field.name
    field.save(f"{uuid4().hex}.webp", content, save=False)
    if old_name and old_name != field.name:
        field.storage.delete(old_name)


def process_upload(uploaded_file):
    """Validate and normalize a member-uploaded image. Re-encoding to WEBP
    drops EXIF (incl. GPS) and bounds dimensions/weight."""
    if uploaded_file.size > MAX_BYTES:
        raise ValidationError("התמונה גדולה מדי (עד 5MB)")
    try:
        img = Image.open(uploaded_file)
        img_format = img.format
        # Read dimensions from the header BEFORE decoding pixels — this is
        # what stops a decompression bomb from OOM-killing the process.
        width, height = img.size
        if width * height > MAX_PIXELS:
            raise ValidationError("התמונה גדולה מדי (רזולוציה)")
        img.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise ValidationError("קובץ התמונה לא תקין")
    if img_format not in _ALLOWED_FORMATS:
        raise ValidationError("פורמט לא נתמך — JPEG, PNG או WEBP")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, "WEBP", quality=85)
    return ContentFile(buf.getvalue())
