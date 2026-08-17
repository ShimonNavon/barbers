from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "קטלוג המספרות"

    def ready(self):
        from . import signals  # noqa: F401  (registers the Grist push hook)
