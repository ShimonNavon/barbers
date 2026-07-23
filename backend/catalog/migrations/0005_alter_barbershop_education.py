from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_barbershop_occupation_alter_barbershop_business_name_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="barbershop",
            name="education",
            field=models.CharField(
                blank=True, max_length=1000, verbose_name="היכן למדת / השתלמויות"
            ),
        ),
    ]
