import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Member(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="member")
    application = models.OneToOneField(
        "catalog.Barbershop", on_delete=models.PROTECT, related_name="member",
        verbose_name="מועמדות")
    display_name = models.CharField("שם תצוגה", max_length=50)
    phone_e164 = models.CharField("טלפון", max_length=16, unique=True)
    avatar = models.ImageField("תמונת פרופיל", upload_to="avatars/",
                               blank=True, null=True)
    bio = models.CharField("על עצמי", max_length=300, blank=True, default="")
    onboarded = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "חבר/ה"
        verbose_name_plural = "חברי קהילה"

    def __str__(self):
        return self.display_name

    # profile facts live on the vetted application — never duplicated
    @property
    def occupation_display(self):
        return self.application.get_occupation_display()

    @property
    def city(self):
        return self.application.city

    @property
    def instagram(self):
        return self.application.instagram


class OtpCode(models.Model):
    MAX_ATTEMPTS = 5
    TTL_MINUTES = 5

    phone_e164 = models.CharField(max_length=16, db_index=True)
    code = models.CharField(max_length=6)
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "קוד כניסה"
        verbose_name_plural = "קודי כניסה"

    @classmethod
    def issue(cls, phone_e164):
        cls.objects.filter(phone_e164=phone_e164, used=False).update(used=True)
        return cls.objects.create(
            phone_e164=phone_e164,
            code=f"{secrets.randbelow(10**6):06d}",
            expires_at=timezone.now() + timedelta(minutes=cls.TTL_MINUTES),
        )

    @classmethod
    def check_code(cls, phone_e164, code):
        otp = (cls.objects
               .filter(phone_e164=phone_e164, used=False,
                       expires_at__gt=timezone.now())
               .order_by("-created_at").first())
        if otp is None:
            return False
        otp.attempts += 1
        correct = otp.code == code
        exhausted = otp.attempts >= cls.MAX_ATTEMPTS
        # correct → consumed (single-use); exhausted → burned (attempt cap)
        otp.used = correct or exhausted
        otp.save(update_fields=["attempts", "used"])
        return correct and otp.attempts <= cls.MAX_ATTEMPTS
