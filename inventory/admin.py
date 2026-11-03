from django.contrib import admin

from .models import Inventory, InventoryLog


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("pharmacy", "medicine", "quantity", "minimum_threshold", "last_updated")
    search_fields = ("pharmacy__name", "medicine__name")


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    """Let administrators inspect audit history without changing it."""

    list_display = (
        "timestamp",
        "pharmacy_name",
        "medicine_name",
        "action",
        "actor_username",
    )
    list_filter = ("action", "timestamp")
    search_fields = (
        "pharmacy_name",
        "medicine_name",
        "actor_username",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp", "-id")
    readonly_fields = (
        "source_inventory_id_snapshot",
        "pharmacy_id_snapshot",
        "pharmacy_name",
        "medicine_id_snapshot",
        "medicine_name",
        "actor_id_snapshot",
        "actor_username",
        "action",
        "changes",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
