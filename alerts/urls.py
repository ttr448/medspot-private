from django.urls import path

from . import views

app_name = "alerts"

urlpatterns = [
    path("<int:pk>/acknowledge/", views.acknowledge_alert, name="acknowledge"),
]
