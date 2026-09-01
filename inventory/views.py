# inventory/views.py
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from users.decorators import role_required
from pharmacies.models import Pharmacy
from medicines.models import Medicine

from .forms import AddMedicineForm, EditInventoryForm
from .models import Inventory


def _get_owned_pharmacy(request):
    """Return the pharmacy owned by the logged-in pharmacist, if any."""
    return Pharmacy.objects.filter(owner=request.user).first()


@role_required("pharmacist", require_verified=True)
def medicine_add(request):
    pharmacy = _get_owned_pharmacy(request)
    if pharmacy is None:
        messages.error(request, "No pharmacy is linked to your account yet.")
        return redirect("pharmacies:dashboard")

    if request.method == "POST":
        form = AddMedicineForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            medicine, _ = Medicine.objects.get_or_create(
                name__iexact=data["name"],
                active_ingredient__iexact=data["active_ingredient"],
                dosage_form__iexact=data["dosage_form"],
                defaults={
                    "name": data["name"],
                    "category": data["category"],
                    "active_ingredient": data["active_ingredient"],
                    "dosage_form": data["dosage_form"],
                },
            )

            try:
                with transaction.atomic():
                    Inventory.objects.create(
                        pharmacy=pharmacy,
                        medicine=medicine,
                        quantity=data["quantity"],
                        minimum_threshold=data["minimum_threshold"],
                    )
            except IntegrityError:
                messages.error(
                    request,
                    f"{medicine.name} is already in your inventory. Edit it instead of adding it again.",
                )
                return redirect("pharmacies:dashboard")

            messages.success(request, "Medicine added successfully.")
            return redirect("pharmacies:dashboard")
    else:
        form = AddMedicineForm()

    return render(request, "inventory/medicine_form.html", {"form": form, "mode": "add"})


@role_required("pharmacist", require_verified=True)
def medicine_edit(request, pk):
    pharmacy = _get_owned_pharmacy(request)
    if pharmacy is None:
        messages.error(request, "No pharmacy is linked to your account yet.")
        return redirect("pharmacies:dashboard")

    inventory = get_object_or_404(Inventory, pk=pk, pharmacy=pharmacy)

    if request.method == "POST":
        form = EditInventoryForm(request.POST)
        if form.is_valid():
            inventory.quantity = form.cleaned_data["quantity"]
            inventory.minimum_threshold = form.cleaned_data["minimum_threshold"]
            inventory.save()
            messages.success(request, "Medicine updated successfully.")
            return redirect("pharmacies:dashboard")
    else:
        form = EditInventoryForm(
            initial={
                "quantity": inventory.quantity,
                "minimum_threshold": inventory.minimum_threshold,
            }
        )

    return render(
        request,
        "inventory/medicine_form.html",
        {"form": form, "mode": "edit", "medicine": inventory.medicine},
    )


@role_required("pharmacist", require_verified=True)
def medicine_delete(request, pk):
    pharmacy = _get_owned_pharmacy(request)
    if pharmacy is None:
        messages.error(request, "No pharmacy is linked to your account yet.")
        return redirect("pharmacies:dashboard")

    inventory = get_object_or_404(Inventory, pk=pk, pharmacy=pharmacy)

    if request.method == "POST":
        medicine_name = inventory.medicine.name
        inventory.delete()
        messages.success(request, f"{medicine_name} deleted successfully.")
        return redirect("pharmacies:dashboard")

    return render(request, "inventory/medicine_confirm_delete.html", {"inventory": inventory})
