# pharmacies/views.py
from django.shortcuts import render

from users.decorators import role_required
from inventory.models import Inventory

from .models import Pharmacy


@role_required("pharmacist", require_verified=True)
def pharmacist_dashboard(request):
    """Display the verified pharmacist's own pharmacy and inventory."""
    pharmacy = Pharmacy.objects.filter(owner=request.user).first()

    inventory_items = []
    if pharmacy is not None:
        inventory_items = (
            Inventory.objects.filter(pharmacy=pharmacy)
            .select_related("medicine")
            .order_by("medicine__name")
        )

    return render(
        request,
        "pharmacies/dashboard.html",
        {"pharmacy": pharmacy, "inventory_items": inventory_items},
    )
