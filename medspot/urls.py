# medspot/urls.py
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("users.urls", namespace="users")),
    path("pharmacies/", include("pharmacies.urls", namespace="pharmacies")),
    path("inventory/", include("inventory.urls", namespace="inventory")),
]
