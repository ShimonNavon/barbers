from django.db import models


class Barbershop(models.Model):
    class Sector(models.TextChoices):
        CERTIFIED = "certified", 'מוסמך — תעודת תמ"ת / אקדמיה מוכרת'
        INDEPENDENT = "independent", "עצמאי — בשלבי למידה והשתלמויות"

    class Occupation(models.TextChoices):
        HAIR = "hair", "מעצב/ת שיער"
        BARBER = "barber", "ברבר"
        MAKEUP = "makeup", "מאפר/ת"
        COSMETICS = "cosmetics", "קוסמטיקאי/ת"
        NAILS = "nails", "מעצב/ת ציפורניים"
        OTHER = "other", "אחר"

    business_name = models.CharField("שם העסק", max_length=150, blank=True, default="")
    owner_name = models.CharField("שם מלא", max_length=120)
    occupation = models.CharField(
        "תחום עיסוק",
        max_length=20,
        choices=Occupation.choices,
        default=Occupation.OTHER,
    )
    phone = models.CharField("טלפון", max_length=30)
    email = models.EmailField("אימייל", max_length=254, blank=True)
    city = models.CharField("עיר", max_length=100, blank=True, default="")
    address = models.CharField("כתובת", max_length=200, blank=True)
    description = models.TextField("על המספרה", blank=True)
    instagram = models.CharField("אינסטגרם", max_length=150, blank=True)
    sector = models.CharField(
        "סטטוס הסמכה",
        max_length=20,
        choices=Sector.choices,
        default=Sector.INDEPENDENT,
    )
    education = models.CharField(
        "היכן למדת / השתלמויות", max_length=1000, blank=True
    )
    created_at = models.DateTimeField("נרשם בתאריך", auto_now_add=True)
    approved = models.BooleanField("אושר", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "מספרה"
        verbose_name_plural = "מספרות"

    def __str__(self):
        return f"{self.business_name} — {self.city}"
