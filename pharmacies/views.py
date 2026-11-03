# pharmacies/views.py
from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import PharmacyWorkingHoursForm

from alerts.models import Alert
from users.decorators import role_required
from inventory.models import Inventory, InventoryLog

from .models import Pharmacy


@role_required("pharmacist", require_verified=True)
def pharmacist_dashboard(request):
    """Display the verified pharmacist's own pharmacy and inventory."""
    pharmacy = Pharmacy.objects.filter(owner=request.user).first()

    working_hours_form = PharmacyWorkingHoursForm(instance=pharmacy) if pharmacy else None

    if (
        request.method == "POST"
        and pharmacy is not None
        and "save_working_hours" in request.POST
    ):
        working_hours_form = PharmacyWorkingHoursForm(request.POST, instance=pharmacy)
        if working_hours_form.is_valid():
            working_hours_form.save()
            messages.success(request, "Pharmacy working hours updated successfully.")
            return redirect("pharmacies:dashboard")

    inventory_items = []
    low_stock_alerts = []
    inventory_logs = []
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
        inventory_logs = InventoryLog.objects.filter(
            pharmacy_id_snapshot=pharmacy.pk
        )[:50]

    return render(
        request,
        "pharmacies/dashboard.html",
        {
            "pharmacy": pharmacy,
            "working_hours_form": working_hours_form,
            "inventory_items": inventory_items,
            "low_stock_alerts": low_stock_alerts,
            "inventory_logs": inventory_logs,
        },
    )
