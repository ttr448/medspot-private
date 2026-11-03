"""Helpers for creating immutable inventory audit records."""

from .models import InventoryLog


def inventory_snapshot(inventory):
    """Capture the inventory and medicine fields relevant to audit history."""
    medicine = inventory.medicine
    return {
        "medicine_name": medicine.name,
        "strength": medicine.strength or "",
        "active_ingredient": medicine.active_ingredient or "",
        "category": medicine.category or "",
        "quantity": inventory.quantity,
        "minimum_threshold": inventory.minimum_threshold,
    }


def record_inventory_change(inventory, actor, action, before_snapshot=None, after_snapshot=None):
    """Append a create, update, or delete event without changing older records."""
    before_snapshot = before_snapshot or {}
    after_snapshot = after_snapshot or {}

    field_labels = [
        ("medicine_name", "Medicine name"),
        ("strength", "Strength"),
        ("active_ingredient", "Active ingredient"),
        ("category", "Category"),
        ("quantity", "Quantity"),
        ("minimum_threshold", "Minimum threshold"),
    ]

    changes = []
    for field_name, label in field_labels:
        before_value = before_snapshot.get(field_name)
        after_value = after_snapshot.get(field_name)
        if before_value != after_value:
            changes.append(
                {
                    "field": label,
                    "before": before_value,
                    "after": after_value,
                }
            )

    actor_id = getattr(actor, "pk", None)
    actor_username = actor.get_username() if actor and hasattr(actor, "get_username") else ""

    return InventoryLog.objects.create(
        source_inventory_id_snapshot=inventory.pk,
        pharmacy_id_snapshot=inventory.pharmacy_id,
        pharmacy_name=inventory.pharmacy.name,
        medicine_id_snapshot=inventory.medicine_id,
        medicine_name=inventory.medicine.name,
        actor_id_snapshot=actor_id,
        actor_username=actor_username,
        action=action,
        changes=changes,
    )
