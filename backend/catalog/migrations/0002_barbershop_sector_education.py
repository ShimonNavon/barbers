from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="barbershop",
            name="sector",
            field=models.CharField(
                choices=[
                    ("certified", 'מוסמך — תעודת תמ"ת / אקדמיה מוכרת'),
                    ("independent", "עצמאי — בשלבי למידה והשתלמויות"),
                ],
                default="independent",
                max_length=20,
                verbose_name="סטטוס הסמכה",
            ),
        ),
        migrations.AddField(
            model_name="barbershop",
            name="education",
            field=models.CharField(
                blank=True, max_length=200, verbose_name="היכן למדת / השתלמויות"
            ),
        ),
    ]
