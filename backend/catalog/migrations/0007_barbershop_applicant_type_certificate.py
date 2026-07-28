from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_alter_barbershop_city"),
    ]

    operations = [
        migrations.AddField(
            model_name="barbershop",
            name="applicant_type",
            field=models.CharField(
                choices=[
                    ("client", "לקוח/ה — רשימת המתנה"),
                    ("professional", "מעצב/ת שיער — מועמדות לקהילה"),
                ],
                default="professional",
                max_length=20,
                verbose_name="סוג פנייה",
            ),
        ),
        migrations.AddField(
            model_name="barbershop",
            name="certificate",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="certificates/",
                verbose_name="תעודת הסמכה",
            ),
        ),
    ]
