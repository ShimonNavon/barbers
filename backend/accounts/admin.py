from django.contrib import admin

from .models import Member, OtpCode


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "phone_e164", "onboarded",
                    "last_seen", "created_at")
    search_fields = ("display_name", "phone_e164")
    readonly_fields = ("created_at", "last_seen")


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    """MVP: the client reads codes here while SMS sending is stubbed."""
    list_display = ("phone_e164", "code", "created_at", "expires_at",
                    "attempts", "used")
    readonly_fields = ("phone_e164", "code", "created_at", "expires_at",
                       "attempts", "used")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False
