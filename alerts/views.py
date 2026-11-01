from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from pharmacies.models import Pharmacy
from users.decorators import role_required

from .models import Alert


@require_POST
@role_required("pharmacist", require_verified=True)
def acknowledge_alert(request, pk):
    pharmacy = Pharmacy.objects.filter(owner=request.user).first()
    if pharmacy is None:
        messages.error(request, "No pharmacy is linked to your account.")
        return redirect("pharmacies:dashboard")

    alert = get_object_or_404(
        Alert,
        pk=pk,
        pharmacy=pharmacy,
        alert_type="low_stock",
    )
    alert.acknowledged = True
    alert.save(update_fields=["acknowledged"])
    messages.success(request, "Low-stock alert dismissed.")
    return redirect("pharmacies:dashboard")
