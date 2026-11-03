from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse

from alerts.models import Alert
from inventory.models import Inventory, InventoryLog
from medicines.models import Medicine
from pharmacies.models import Pharmacy


User = get_user_model()


class InventoryCrudTests(TestCase):
    def setUp(self):
        self.pharmacist = User.objects.create_user(
            username="pharmacist1",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.pharmacy = Pharmacy.objects.create(
            name="ABC Pharmacy",
            address="123 Main Street",
            owner=self.pharmacist,
        )
        self.medicine = Medicine.objects.create(
            name="Panadol",
            active_ingredient="Paracetamol",
            category="Analgesic",
            strength="500 mg",
        )
        self.inventory = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            quantity=20,
            minimum_threshold=5,
        )
        self.client.force_login(self.pharmacist)

    def test_pharmacist_can_open_add_medicine_page(self):
        response = self.client.get(reverse("inventory:medicine_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add Medicine")

    def test_pharmacist_can_add_medicine_to_own_pharmacy(self):
        response = self.client.post(
            reverse("inventory:medicine_add"),
            {
                "name": "Amoxicillin",
                "category": "Antibiotic",
                "active_ingredient": "Amoxicillin",
                "strength": "250 mg",
                "quantity": 12,
                "minimum_threshold": 3,
            },
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        added_item = Inventory.objects.get(
            pharmacy=self.pharmacy,
            medicine__name="Amoxicillin",
        )
        self.assertEqual(added_item.quantity, 12)
        self.assertEqual(added_item.minimum_threshold, 3)
        self.assertEqual(added_item.medicine.strength, "250 mg")

    def test_adding_medicine_creates_an_audit_log_with_actor_and_details(self):
        response = self.client.post(
            reverse("inventory:medicine_add"),
            {
                "name": "Amoxicillin",
                "category": "Antibiotic",
                "active_ingredient": "Amoxicillin",
                "strength": "250 mg",
                "quantity": 12,
                "minimum_threshold": 3,
            },
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        added_item = Inventory.objects.get(
            pharmacy=self.pharmacy,
            medicine__name="Amoxicillin",
        )
        log = InventoryLog.objects.get(source_inventory_id_snapshot=added_item.pk)

        self.assertEqual(log.action, "create")
        self.assertEqual(log.actor_id_snapshot, self.pharmacist.pk)
        self.assertEqual(log.actor_username, self.pharmacist.username)
        self.assertEqual(log.pharmacy_id_snapshot, self.pharmacy.pk)
        self.assertEqual(log.pharmacy_name, self.pharmacy.name)
        self.assertEqual(log.medicine_name, "Amoxicillin")
        self.assertIsNotNone(log.timestamp)
        self.assertIn(
            {"field": "Quantity", "before": None, "after": 12},
            log.changes,
        )
        self.assertIn(
            {"field": "Minimum threshold", "before": None, "after": 3},
            log.changes,
        )

    def test_duplicate_medicine_cannot_be_added_twice_to_same_pharmacy(self):
        data = {
            "name": "Panadol",
            "category": "Analgesic",
            "active_ingredient": "Paracetamol",
            "strength": "500 mg",
            "quantity": 15,
            "minimum_threshold": 5,
        }

        first_response = self.client.post(reverse("inventory:medicine_add"), data)
        second_response = self.client.post(reverse("inventory:medicine_add"), data)

        self.assertRedirects(first_response, reverse("pharmacies:dashboard"))
        self.assertRedirects(second_response, reverse("pharmacies:dashboard"))
        self.assertEqual(
            Inventory.objects.filter(pharmacy=self.pharmacy, medicine=self.medicine).count(),
            1,
        )
        # Both add attempts are rejected because this inventory already exists.
        # A rejected operation does not change stock, so it must not create an audit log.
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 20)
        self.assertEqual(
            InventoryLog.objects.filter(
                pharmacy_id_snapshot=self.pharmacy.pk,
                medicine_name="Panadol",
            ).count(),
            0,
        )

    def test_negative_quantity_is_rejected(self):
        response = self.client.post(
            reverse("inventory:medicine_add"),
            {
                "name": "Amoxicillin",
                "category": "Antibiotic",
                "active_ingredient": "Amoxicillin",
                "strength": "250 mg",
                "quantity": -1,
                "minimum_threshold": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Inventory.objects.filter(pharmacy=self.pharmacy, medicine__name="Amoxicillin").exists()
        )

    def test_pharmacist_can_edit_own_inventory(self):
        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": self.inventory.pk}),
            {"quantity": 8, "minimum_threshold": 4},
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 8)
        self.assertEqual(self.inventory.minimum_threshold, 4)

    def test_pharmacist_can_edit_medicine_profile_and_shared_pharmacy_logs_are_created(self):
        other_user = User.objects.create_user(
            username="second_pharmacist",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        other_pharmacy = Pharmacy.objects.create(
            name="Other Pharmacy",
            address="456 Side Street",
            owner=other_user,
        )
        other_inventory = Inventory.objects.create(
            pharmacy=other_pharmacy,
            medicine=self.medicine,
            quantity=1,
            minimum_threshold=2,
        )
        other_alert = Alert.objects.create(
            pharmacy=other_pharmacy,
            medicine=self.medicine,
            alert_type="low_stock",
            message="Panadol is low in stock: 1 available; minimum threshold is 2.",
        )

        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": self.inventory.pk}),
            {
                "name": "Panadol Extra",
                "active_ingredient": "Paracetamol",
                "category": "Pain relief",
                "strength": "650 mg",
                "quantity": 8,
                "minimum_threshold": 4,
            },
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.name, "Panadol Extra")
        self.assertEqual(self.medicine.active_ingredient, "Paracetamol")
        self.assertEqual(self.medicine.category, "Pain relief")
        self.assertEqual(self.medicine.strength, "650 mg")

        self.inventory.refresh_from_db()
        other_inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 8)
        self.assertEqual(other_inventory.quantity, 1)

        own_log = InventoryLog.objects.get(
            pharmacy_id_snapshot=self.pharmacy.pk,
            source_inventory_id_snapshot=self.inventory.pk,
            action="update",
        )
        other_log = InventoryLog.objects.get(
            pharmacy_id_snapshot=other_pharmacy.pk,
            source_inventory_id_snapshot=other_inventory.pk,
            action="update",
        )
        self.assertIn(
            {"field": "Medicine name", "before": "Panadol", "after": "Panadol Extra"},
            own_log.changes,
        )
        self.assertIn(
            {"field": "Strength", "before": "500 mg", "after": "650 mg"},
            other_log.changes,
        )
        self.assertNotIn(
            "Quantity",
            [change["field"] for change in other_log.changes],
        )
        other_alert.refresh_from_db()
        self.assertIn("Panadol Extra", other_alert.message)
        self.assertIn("1 available", other_alert.message)

    def test_medicine_profile_edit_rejects_an_empty_medicine_name(self):
        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": self.inventory.pk}),
            {
                "name": "   ",
                "active_ingredient": "Paracetamol",
                "category": "Analgesic",
                "strength": "500 mg",
                "quantity": 8,
                "minimum_threshold": 4,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.inventory.refresh_from_db()
        self.medicine.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 20)
        self.assertEqual(self.medicine.name, "Panadol")
        self.assertContains(response, "Medicine name is required.")

    def test_submitting_unchanged_inventory_values_does_not_create_a_log(self):
        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": self.inventory.pk}),
            {"quantity": 20, "minimum_threshold": 5},
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.assertFalse(InventoryLog.objects.exists())

    def test_editing_inventory_creates_audit_log_with_before_and_after_values(self):
        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": self.inventory.pk}),
            {"quantity": 8, "minimum_threshold": 4},
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        log = InventoryLog.objects.get(
            source_inventory_id_snapshot=self.inventory.pk,
            action="update",
        )
        self.assertEqual(log.actor_id_snapshot, self.pharmacist.pk)
        self.assertIn(
            {"field": "Quantity", "before": 20, "after": 8},
            log.changes,
        )
        self.assertIn(
            {"field": "Minimum threshold", "before": 5, "after": 4},
            log.changes,
        )

    def test_pharmacist_cannot_edit_another_pharmacy_inventory(self):
        other_user = User.objects.create_user(
            username="pharmacist2",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        other_pharmacy = Pharmacy.objects.create(
            name="Other Pharmacy",
            address="456 Side Street",
            owner=other_user,
        )
        other_inventory = Inventory.objects.create(
            pharmacy=other_pharmacy,
            medicine=self.medicine,
            quantity=9,
            minimum_threshold=2,
        )

        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": other_inventory.pk}),
            {"quantity": 100, "minimum_threshold": 1},
        )

        self.assertEqual(response.status_code, 404)
        other_inventory.refresh_from_db()
        self.assertEqual(other_inventory.quantity, 9)

    def test_pharmacist_can_delete_own_inventory_without_deleting_shared_medicine(self):
        response = self.client.post(
            reverse("inventory:medicine_delete", kwargs={"pk": self.inventory.pk})
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.assertFalse(Inventory.objects.filter(pk=self.inventory.pk).exists())
        self.assertTrue(Medicine.objects.filter(pk=self.medicine.pk).exists())

    def test_deleting_inventory_keeps_its_audit_log(self):
        inventory_id = self.inventory.pk
        response = self.client.post(
            reverse("inventory:medicine_delete", kwargs={"pk": inventory_id})
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.assertFalse(Inventory.objects.filter(pk=inventory_id).exists())

        log = InventoryLog.objects.get(
            source_inventory_id_snapshot=inventory_id,
            action="delete",
        )
        self.assertEqual(log.medicine_name, "Panadol")
        self.assertEqual(log.actor_id_snapshot, self.pharmacist.pk)
        self.assertIn(
            {"field": "Quantity", "before": 20, "after": None},
            log.changes,
        )

    def test_audit_log_records_cannot_be_updated_or_deleted(self):
        log = InventoryLog.objects.create(
            source_inventory_id_snapshot=self.inventory.pk,
            pharmacy_id_snapshot=self.pharmacy.pk,
            pharmacy_name=self.pharmacy.name,
            medicine_id_snapshot=self.medicine.pk,
            medicine_name=self.medicine.name,
            actor_id_snapshot=self.pharmacist.pk,
            actor_username=self.pharmacist.username,
            action="update",
            changes=[{"field": "Quantity", "before": 20, "after": 10}],
        )

        log.actor_username = "changed-user"
        with self.assertRaises(ValidationError):
            log.save()

        with self.assertRaises(ValidationError):
            InventoryLog.objects.filter(pk=log.pk).update(actor_username="changed-user")

        with self.assertRaises(ValidationError):
            log.delete()

        with self.assertRaises(ValidationError):
            InventoryLog.objects.filter(pk=log.pk).delete()

        with self.assertRaises(ValidationError):
            InventoryLog.objects.bulk_update([log], ["actor_username"])

        log.refresh_from_db()
        self.assertEqual(log.actor_username, self.pharmacist.username)

    def test_deleting_inventory_closes_its_active_low_stock_alert(self):
        alert = Alert.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            alert_type="low_stock",
            message="Panadol is low in stock.",
        )

        response = self.client.post(
            reverse("inventory:medicine_delete", kwargs={"pk": self.inventory.pk})
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)

    def test_pharmacist_cannot_delete_another_pharmacy_inventory(self):
        other_user = User.objects.create_user(
            username="pharmacist2",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        other_pharmacy = Pharmacy.objects.create(
            name="Other Pharmacy",
            address="456 Side Street",
            owner=other_user,
        )
        other_inventory = Inventory.objects.create(
            pharmacy=other_pharmacy,
            medicine=self.medicine,
            quantity=9,
            minimum_threshold=2,
        )

        response = self.client.post(
            reverse("inventory:medicine_delete", kwargs={"pk": other_inventory.pk})
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Inventory.objects.filter(pk=other_inventory.pk).exists())

    def test_unverified_pharmacist_cannot_manage_inventory(self):
        unverified = User.objects.create_user(
            username="pending",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=False,
        )
        self.client.force_login(unverified)

        response = self.client.get(reverse("inventory:medicine_add"))

        self.assertRedirects(
            response,
            reverse("users:access_denied"),
            target_status_code=403,
        )

    def test_patient_cannot_manage_inventory(self):
        patient = User.objects.create_user(
            username="patient1",
            password="Strong-Test-Password-2026!",
            role="patient",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(patient)

        response = self.client.get(reverse("inventory:medicine_add"))

        self.assertRedirects(
            response,
            reverse("users:access_denied"),
            target_status_code=403,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(reverse("inventory:medicine_add"))

        self.assertRedirects(response, reverse("users:login"))


    def test_editing_stock_down_to_threshold_creates_low_stock_alert(self):
        response = self.client.post(
            reverse("inventory:medicine_edit", kwargs={"pk": self.inventory.pk}),
            {"quantity": 5, "minimum_threshold": 5},
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        alert = Alert.objects.get(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            alert_type="low_stock",
        )
        self.assertFalse(alert.acknowledged)
        self.assertIn("5 available", alert.message)

    def test_adding_medicine_at_zero_quantity_creates_low_stock_alert(self):
        response = self.client.post(
            reverse("inventory:medicine_add"),
            {
                "name": "New Medicine",
                "category": "General",
                "active_ingredient": "New Ingredient",
                "strength": "500 mg",
                "quantity": 0,
                "minimum_threshold": 5,
            },
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        new_inventory = Inventory.objects.get(
            pharmacy=self.pharmacy,
            medicine__name="New Medicine",
        )
        alert = Alert.objects.get(
            pharmacy=self.pharmacy,
            medicine=new_inventory.medicine,
            alert_type="low_stock",
        )
        self.assertFalse(alert.acknowledged)
        self.assertIn("0 available", alert.message)


class InventoryLogAdminTests(TestCase):
    def test_admin_can_view_logs_but_cannot_add_change_or_delete_them(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from inventory.admin import InventoryLogAdmin

        admin_user = User.objects.create_superuser(
            username="audit_admin",
            email="audit-admin@example.com",
            password="Strong-Test-Password-2026!",
        )
        request = RequestFactory().get("/admin/inventory/inventorylog/")
        request.user = admin_user
        model_admin = InventoryLogAdmin(InventoryLog, AdminSite())

        self.assertTrue(model_admin.has_view_permission(request))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
