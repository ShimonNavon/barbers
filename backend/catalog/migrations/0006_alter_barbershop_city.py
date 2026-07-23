from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_alter_barbershop_education"),
    ]

    operations = [
        migrations.AlterField(
            model_name="barbershop",
            name="city",
            field=models.CharField(
                blank=True, default="", max_length=100, verbose_name="עיר"
            ),
        ),
    ]
