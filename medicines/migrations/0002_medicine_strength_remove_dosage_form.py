from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("medicines", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="medicine",
            name="strength",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.RemoveField(
            model_name="medicine",
            name="dosage_form",
        ),
    ]
