# users/views.py
import math

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout, get_user_model
from django.contrib.auth.views import LoginView
from django.views import View
from django.db.models import Q

from .forms import PatientRegistrationForm, PharmacistRegistrationForm
from users.decorators import role_required
from inventory.models import Inventory

# Get the custom user model (CustomUser)
User = get_user_model()


def _parse_coordinate(value, minimum, maximum):
    """Return a valid finite coordinate, or None when the input is invalid."""
    try:
        coordinate = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(coordinate) or not minimum <= coordinate <= maximum:
        return None

    return coordinate


def _haversine_distance_km(latitude_1, longitude_1, latitude_2, longitude_2):
    """Calculate the great-circle distance between two points in kilometres."""
    earth_radius_km = 6371.0

    latitude_1 = math.radians(latitude_1)
    longitude_1 = math.radians(longitude_1)
    latitude_2 = math.radians(latitude_2)
    longitude_2 = math.radians(longitude_2)

    latitude_difference = latitude_2 - latitude_1
    longitude_difference = longitude_2 - longitude_1

    haversine_value = (
        math.sin(latitude_difference / 2) ** 2
        + math.cos(latitude_1)
        * math.cos(latitude_2)
        * math.sin(longitude_difference / 2) ** 2
    )

    central_angle = 2 * math.asin(min(1, math.sqrt(haversine_value)))
    return earth_radius_km * central_angle


def patient_register(request):
    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful. You can now log in.")
            return redirect("users:login")
    else:
        form = PatientRegistrationForm()
    return render(request, "users/registration_patient.html", {"form": form})


def pharmacist_register(request):
    if request.method == "POST":
        form = PharmacistRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration submitted, pending admin approval.")
            return redirect("users:login")
    else:
        form = PharmacistRegistrationForm()
    return render(request, "users/registration_pharmacist.html", {"form": form})


class RoleBasedLoginView(LoginView):
    template_name = "registration/login.html"

    def form_invalid(self, form):
        # Extract username entered in the login form
        username = form.data.get("username")

        if username:
            # Check if user exists in the database
            user = User.objects.filter(username=username).first()

            # If user exists, is a pharmacist, but not activated yet
            if user and getattr(user, "role", None) == "pharmacist" and not user.is_active:
                messages.error(
                    self.request,
                    "Your registration is pending admin approval. Please wait for activation."
                )
                return self.render_to_response(self.get_context_data(form=form))

        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user

        # Handle redirects by role
        if getattr(user, "role", None) == "patient":
            return redirect("users:patient_search")
        if getattr(user, "role", None) == "pharmacist":
            return redirect("pharmacies:dashboard")
        if user.is_staff or getattr(user, "role", None) == "admin":
            return redirect("/admin/")
        return response


class CustomLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("users:login")

    def post(self, request):
        logout(request)
        return redirect("users:login")


def patient_search(request):
    # Only logged-in patients can search for medicine.
    if not request.user.is_authenticated or getattr(request.user, "role", None) != "patient":
        messages.error(request, "Please log in as a patient to access this page.")
        return redirect("users:login")

    query = request.GET.get("q", "").strip()
    patient_latitude = _parse_coordinate(request.GET.get("lat"), -90, 90)
    patient_longitude = _parse_coordinate(request.GET.get("lng"), -180, 180)
    has_patient_location = (
        patient_latitude is not None and patient_longitude is not None
    )

    location_error = False
    if ("lat" in request.GET or "lng" in request.GET) and not has_patient_location:
        location_error = True

    results = Inventory.objects.none()

    if query:
        results = (
            Inventory.objects.filter(
                quantity__gt=0,
                pharmacy__owner__is_active=True,
                pharmacy__owner__is_verified=True,
                pharmacy__owner__role="pharmacist",
            )
            .filter(
                Q(medicine__name__icontains=query)
                | Q(medicine__active_ingredient__icontains=query)
            )
            .select_related("medicine", "pharmacy")
            .order_by("medicine__name", "pharmacy__name")
        )

    # Calculate distances only after the patient explicitly shares their location.
    if has_patient_location and query:
        results = list(results)
        for item in results:
            pharmacy_latitude = _parse_coordinate(item.pharmacy.latitude, -90, 90)
            pharmacy_longitude = _parse_coordinate(item.pharmacy.longitude, -180, 180)

            if pharmacy_latitude is None or pharmacy_longitude is None:
                item.distance_km = None
            else:
                item.distance_km = round(
                    _haversine_distance_km(
                        patient_latitude,
                        patient_longitude,
                        pharmacy_latitude,
                        pharmacy_longitude,
                    ),
                    2,
                )

        results.sort(
            key=lambda item: (
                item.distance_km is None,
                item.distance_km if item.distance_km is not None else float("inf"),
            )
        )

    map_locations = []
    for item in results:
        pharmacy_latitude = _parse_coordinate(item.pharmacy.latitude, -90, 90)
        pharmacy_longitude = _parse_coordinate(item.pharmacy.longitude, -180, 180)

        if pharmacy_latitude is not None and pharmacy_longitude is not None:
            map_locations.append(
                {
                    "pharmacy_name": item.pharmacy.name,
                    "address": item.pharmacy.address,
                    "medicine_name": item.medicine.name,
                    "quantity": item.quantity,
                    "lat": pharmacy_latitude,
                    "lng": pharmacy_longitude,
                    "distance_km": getattr(item, "distance_km", None),
                }
            )

    nearest_pharmacy = None
    if has_patient_location and isinstance(results, list):
        nearest_pharmacy = next(
            (item for item in results if item.distance_km is not None),
            None,
        )

    return render(
        request,
        "users/patient_search.html",
        {
            "query": query,
            "results": results,
            "map_locations": map_locations,
            "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY,
            "patient_latitude": patient_latitude,
            "patient_longitude": patient_longitude,
            "has_patient_location": has_patient_location,
            "location_error": location_error,
            "nearest_pharmacy": nearest_pharmacy,
        },
    )


def access_denied(request):
    return render(request, "users/access_denied.html", status=403)


@role_required("admin")
def admin_dashboard(request):
    return render(request, "users/admin_dashboard.html")
