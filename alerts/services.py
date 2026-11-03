from django.utils import timezone

from .models import Alert


def update_low_stock_alert(inventory, user, previous_was_low=None):
    """
    Keep one low-stock alert for a pharmacy/medicine pair.

    An alert is created when stock first becomes low. If stock rises above
    its threshold, the pending alert is closed. If stock later becomes low
    again, an acknowledged alert is reopened instead of creating duplicates.
    """
    is_low = inventory.quantity <= inventory.minimum_threshold
    message = (
        f"{inventory.medicine.name} is low in stock: "
        f"{inventory.quantity} available; minimum threshold is "
        f"{inventory.minimum_threshold}."
    )

    alert = (
        Alert.objects.filter(
            pharmacy=inventory.pharmacy,
            medicine=inventory.medicine,
            alert_type="low_stock",
        )
        .order_by("-created_at")
        .first()
    )

    if is_low:
        if alert is None:
            return Alert.objects.create(
                pharmacy=inventory.pharmacy,
                medicine=inventory.medicine,
                created_by=user,
                alert_type="low_stock",
                message=message,
            )

        # Reopen an old alert only when stock transitions from normal to low.
        if previous_was_low is False and alert.acknowledged:
            alert.acknowledged = False
            alert.created_by = user
            alert.message = message
            alert.created_at = timezone.now()
            alert.save(
                update_fields=["acknowledged", "created_by", "message", "created_at"]
            )
        elif not alert.acknowledged and alert.message != message:
            alert.message = message
            alert.save(update_fields=["message"])

        return alert

    # Treat an alert as resolved when stock rises above the threshold.
    if alert is not None and not alert.acknowledged:
        alert.acknowledged = True
        alert.message = f"{inventory.medicine.name} stock is back above its minimum threshold."
        alert.save(update_fields=["acknowledged", "message"])

    return alert


def refresh_low_stock_alert_message(inventory):
    """Update an active low-stock message after a shared medicine profile changes."""
    if inventory.quantity > inventory.minimum_threshold:
        return None

    alert = (
        Alert.objects.filter(
            pharmacy=inventory.pharmacy,
            medicine=inventory.medicine,
            alert_type="low_stock",
            acknowledged=False,
        )
        .order_by("-created_at")
        .first()
    )
    if alert is None:
        return None

    message = (
        f"{inventory.medicine.name} is low in stock: "
        f"{inventory.quantity} available; minimum threshold is "
        f"{inventory.minimum_threshold}."
    )
    if alert.message != message:
        alert.message = message
        alert.save(update_fields=["message"])
    return alert


def resolve_low_stock_alert(inventory):
    """Close an active alert when the pharmacy removes the medicine from stock."""
    Alert.objects.filter(
        pharmacy=inventory.pharmacy,
        medicine=inventory.medicine,
        alert_type="low_stock",
        acknowledged=False,
    ).update(
        acknowledged=True,
        message=f"{inventory.medicine.name} was removed from this pharmacy's available stock list.",
    )
