import mimetypes

from django.apps import AppConfig


def ensure_mime_types():
    """python:3.12-slim has no .webp mapping — without it Django's media
    serve sends application/octet-stream and nosniff blocks every image."""
    mimetypes.add_type("image/webp", ".webp")


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "חברי קהילה"

    def ready(self):
        ensure_mime_types()
