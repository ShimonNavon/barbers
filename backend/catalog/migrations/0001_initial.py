from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Barbershop",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_name", models.CharField(max_length=150, verbose_name="שם המספרה")),
                ("owner_name", models.CharField(max_length=120, verbose_name="שם הבעלים")),
                ("phone", models.CharField(max_length=30, verbose_name="טלפון")),
                ("city", models.CharField(max_length=100, verbose_name="עיר")),
                ("address", models.CharField(blank=True, max_length=200, verbose_name="כתובת")),
                ("description", models.TextField(blank=True, verbose_name="על המספרה")),
                ("instagram", models.CharField(blank=True, max_length=150, verbose_name="אינסטגרם")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="נרשם בתאריך")),
                ("approved", models.BooleanField(default=False, verbose_name="אושר")),
            ],
            options={
                "verbose_name": "מספרה",
                "verbose_name_plural": "מספרות",
                "ordering": ["-created_at"],
            },
        ),
    ]
