from django.contrib import admin
from .models import Medicine

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("name", "strength", "active_ingredient", "category")
    search_fields = ("name", "active_ingredient", "category")