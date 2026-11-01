# pharmacies/views.py
from django.shortcuts import render

from alerts.models import Alert
from users.decorators import role_required
from inventory.models import Inventory

from .models import Pharmacy


@role_required("pharmacist", require_verified=True)
def pharmacist_dashboard(request):
    """Display the verified pharmacist's own pharmacy and inventory."""
    pharmacy = Pharmacy.objects.filter(owner=request.user).first()

    inventory_items = []
    low_stock_alerts = []
    if pharmacy is not None:
        inventory_items = (
            Inventory.objects.filter(pharmacy=pharmacy)
            .select_related("medicine")
            .order_by("medicine__name")
        )
        low_stock_alerts = (
            Alert.objects.filter(
                pharmacy=pharmacy,
                alert_type="low_stock",
                acknowledged=False,
            )
            .select_related("medicine")
            .order_by("-created_at")
        )

    return render(
        request,
        "pharmacies/dashboard.html",
        {
            "pharmacy": pharmacy,
            "inventory_items": inventory_items,
            "low_stock_alerts": low_stock_alerts,
        },
    )
