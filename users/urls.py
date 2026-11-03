#name=users/urls.py
from django.urls import path
from . import views

app_name = "users"

urlpatterns = [
    path("register/patient/", views.patient_register, name="register_patient"),
    path("register/pharmacist/", views.pharmacist_register, name="register_pharmacist"),
    path("login/", views.RoleBasedLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("patient/search/", views.patient_search, name="patient_search"),
    path("patient/medicine-suggestions/", views.medicine_suggestions, name="medicine_suggestions"),
    path("access-denied/", views.access_denied, name="access_denied"),
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
]