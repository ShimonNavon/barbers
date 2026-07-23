from django.contrib import admin

from .models import Barbershop


@admin.register(Barbershop)
class BarbershopAdmin(admin.ModelAdmin):
    list_display = (
        "owner_name",
        "occupation",
        "phone",
        "email",
        "city",
        "sector",
        "education",
        "created_at",
        "approved",
    )
    list_filter = ("approved", "occupation", "sector", "city", "created_at")
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
