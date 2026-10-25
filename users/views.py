# users/views.py
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

    return render(
        request,
        "users/patient_search.html",
        {"query": query, "results": results},
    )


def access_denied(request):
    return render(request, "users/access_denied.html", status=403)


@role_required("admin")
def admin_dashboard(request):
    return render(request, "users/admin_dashboard.html")
