# inventory/urls.py
from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("medicine/add/", views.medicine_add, name="medicine_add"),
    path("medicine/<int:pk>/edit/", views.medicine_edit, name="medicine_edit"),
    path("medicine/<int:pk>/delete/", views.medicine_delete, name="medicine_delete"),
]
