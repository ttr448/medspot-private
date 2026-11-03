from django.db import models
from django.core.exceptions import ValidationError
from pharmacies.models import Pharmacy
from medicines.models import Medicine

class Inventory(models.Model):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="inventories")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="inventories")
    quantity = models.IntegerField(default=0)
    minimum_threshold = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("pharmacy", "medicine")

    def __str__(self):
        return f"{self.medicine} @ {self.pharmacy}: {self.quantity}"


class ImmutableQuerySet(models.QuerySet):
    """Block normal ORM operations that would alter or remove audit records."""

    def update(self, **kwargs):
        raise ValidationError("Inventory update logs are immutable.")

    def delete(self):
        raise ValidationError("Inventory update logs cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Inventory update logs are immutable.")

    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Inventory update logs cannot be upserted.")
        return super().bulk_create(objs, **kwargs)


class ImmutableLogManager(models.Manager.from_queryset(ImmutableQuerySet)):
    pass


class InventoryLog(models.Model):
    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    ]

    # Snapshot identifiers/names are stored instead of foreign keys so the
    # audit history remains intact if related records are later removed.
    source_inventory_id_snapshot = models.PositiveBigIntegerField()
    pharmacy_id_snapshot = models.PositiveBigIntegerField(db_index=True)
    pharmacy_name = models.CharField(max_length=255)
    medicine_id_snapshot = models.PositiveBigIntegerField()
    medicine_name = models.CharField(max_length=255)

    actor_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    actor_username = models.CharField(max_length=150, blank=True, default="")

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changes = models.JSONField(default=list)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = ImmutableLogManager()

    class Meta:
        ordering = ("-timestamp", "-id")
        verbose_name = "Inventory update log"
        verbose_name_plural = "Inventory update logs"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Inventory update logs are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory update logs cannot be deleted.")

    def __str__(self):
        return f"{self.get_action_display()} - {self.medicine_name} at {self.pharmacy_name}"
