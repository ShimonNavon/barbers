from django.contrib import admin

from .models import Barbershop


@admin.register(Barbershop)
class BarbershopAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "owner_name",
        "phone",
        "city",
        "address",
        "instagram",
        "sector",
        "education",
        "created_at",
        "approved",
    )
    list_filter = ("approved", "sector", "city", "created_at")
    list_editable = ("approved",)
    search_fields = (
        "business_name",
        "owner_name",
        "phone",
        "city",
        "address",
        "education",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
