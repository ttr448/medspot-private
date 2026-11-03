from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_inventory_id_snapshot", models.PositiveBigIntegerField()),
                ("pharmacy_id_snapshot", models.PositiveBigIntegerField(db_index=True)),
                ("pharmacy_name", models.CharField(max_length=255)),
                ("medicine_id_snapshot", models.PositiveBigIntegerField()),
                ("medicine_name", models.CharField(max_length=255)),
                ("actor_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("actor_username", models.CharField(blank=True, default="", max_length=150)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("create", "Create"),
                            ("update", "Update"),
                            ("delete", "Delete"),
                        ],
                        max_length=10,
                    ),
                ),
                ("changes", models.JSONField(default=list)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "Inventory update log",
                "verbose_name_plural": "Inventory update logs",
                "ordering": ("-timestamp", "-id"),
            },
        ),
    ]
