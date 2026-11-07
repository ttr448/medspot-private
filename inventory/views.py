# inventory/views.py
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from alerts.services import (
    refresh_low_stock_alert_message,
    resolve_low_stock_alert,
    update_low_stock_alert,
)
from users.decorators import role_required
from pharmacies.models import Pharmacy
from medicines.models import Medicine

from .forms import AddMedicineForm, BatchUploadForm, EditInventoryForm
from .importers import BatchUploadError, import_medicine_rows, parse_medicine_upload
from .models import Inventory
from .services import inventory_snapshot, record_inventory_change


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
                strength__iexact=data["strength"],
                defaults={
                    "name": data["name"],
                    "category": data["category"],
                    "active_ingredient": data["active_ingredient"],
                    "strength": data["strength"],
                },
            )

            try:
                with transaction.atomic():
                    inventory = Inventory.objects.create(
                        pharmacy=pharmacy,
                        medicine=medicine,
                        quantity=data["quantity"],
                        minimum_threshold=data["minimum_threshold"],
                    )
                    record_inventory_change(
                        inventory,
                        request.user,
                        "create",
                        before_snapshot={},
                        after_snapshot=inventory_snapshot(inventory),
                    )
            except IntegrityError:
                messages.error(
                    request,
                    f"{medicine.name} is already in your inventory. Edit it instead of adding it again.",
                )
                return redirect("pharmacies:dashboard")

            update_low_stock_alert(inventory, request.user, previous_was_low=False)
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
            previous_was_low = inventory.quantity <= inventory.minimum_threshold
            inventory.quantity = form.cleaned_data["quantity"]
            inventory.minimum_threshold = form.cleaned_data["minimum_threshold"]

            # A Medicine record can be shared by several pharmacies. Keep a
            # before-snapshot for each listing so every affected pharmacy gets
            # an accurate audit entry when its shared profile is changed.
            related_inventories = list(
                Inventory.objects.filter(medicine=inventory.medicine)
                .select_related("pharmacy", "medicine")
            )
            before_snapshots = {
                item.pk: inventory_snapshot(item)
                for item in related_inventories
            }

            medicine = inventory.medicine
            if form.profile_submitted:
                medicine.name = form.cleaned_data["name"]
                medicine.active_ingredient = form.cleaned_data["active_ingredient"]
                medicine.category = form.cleaned_data["category"]
                medicine.strength = form.cleaned_data["strength"]

            with transaction.atomic():
                if form.profile_submitted:
                    medicine.save()

                inventory.save()

                for related_inventory in related_inventories:
                    related_inventory.medicine = medicine
                    if related_inventory.pk == inventory.pk:
                        related_inventory.quantity = inventory.quantity
                        related_inventory.minimum_threshold = inventory.minimum_threshold

                    record_inventory_change(
                        related_inventory,
                        request.user,
                        "update",
                        before_snapshot=before_snapshots[related_inventory.pk],
                        after_snapshot=inventory_snapshot(related_inventory),
                    )
                    if form.profile_submitted:
                        refresh_low_stock_alert_message(related_inventory)

            inventory.refresh_from_db()
            update_low_stock_alert(
                inventory,
                request.user,
                previous_was_low=previous_was_low,
            )
            if form.profile_submitted:
                messages.success(
                    request,
                    "Medicine details and stock updated successfully.",
                )
            else:
                messages.success(request, "Medicine stock updated successfully.")
            return redirect("pharmacies:dashboard")
    else:
        form = EditInventoryForm(
            initial={
                "name": inventory.medicine.name,
                "active_ingredient": inventory.medicine.active_ingredient,
                "category": inventory.medicine.category,
                "strength": inventory.medicine.strength,
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
        before_snapshot = inventory_snapshot(inventory)
        with transaction.atomic():
            resolve_low_stock_alert(inventory)
            record_inventory_change(
                inventory,
                request.user,
                "delete",
                before_snapshot=before_snapshot,
                after_snapshot={},
            )
            inventory.delete()
        messages.success(request, f"{medicine_name} deleted successfully.")
        return redirect("pharmacies:dashboard")

    return render(request, "inventory/medicine_confirm_delete.html", {"inventory": inventory})


@role_required("pharmacist", require_verified=True)
def medicine_batch_upload(request):
    pharmacy = _get_owned_pharmacy(request)
    if pharmacy is None:
        messages.error(request, "No pharmacy is linked to your account yet.")
        return redirect("pharmacies:dashboard")

    batch_errors = []
    if request.method == "POST":
        form = BatchUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                rows = parse_medicine_upload(form.cleaned_data["file"])
            except BatchUploadError as exc:
                batch_errors = exc.errors
            else:
                result = import_medicine_rows(pharmacy, request.user, rows)
                messages.success(
                    request,
                    (
                        f"Import completed: {result['created']} medicines added and "
                        f"{result['updated']} existing pharmacy records updated."
                    ),
                )
                return redirect("pharmacies:dashboard")
    else:
        form = BatchUploadForm()

    return render(
        request,
        "inventory/batch_upload.html",
        {"form": form, "batch_errors": batch_errors},
    )
