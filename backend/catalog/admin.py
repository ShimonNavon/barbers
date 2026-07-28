from django.contrib import admin
from django.utils.html import format_html

from .models import Barbershop


@admin.register(Barbershop)
class BarbershopAdmin(admin.ModelAdmin):
    list_display = (
        "owner_name",
        "applicant_type",
        "occupation",
        "phone",
        "email",
        "city",
        "sector",
        "education",
        "certificate_link",
        "created_at",
        "approved",
    )
    list_filter = ("applicant_type", "approved", "occupation", "sector", "city", "created_at")
    list_editable = ("approved",)
    search_fields = (
        "owner_name",
        "phone",
        "email",
        "city",
        "education",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="תעודה")
    def certificate_link(self, obj):
        if obj.certificate:
            return format_html('<a href="{}" target="_blank">צפייה</a>', obj.certificate.url)
        return "—"
