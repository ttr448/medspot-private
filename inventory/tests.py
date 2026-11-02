from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alerts.models import Alert
from inventory.models import Inventory
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
            dosage_form="Tablet",
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
                "dosage_form": "Capsule",
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

    def test_duplicate_medicine_cannot_be_added_twice_to_same_pharmacy(self):
        data = {
            "name": "Panadol",
            "category": "Analgesic",
            "active_ingredient": "Paracetamol",
            "dosage_form": "Tablet",
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

    def test_negative_quantity_is_rejected(self):
        response = self.client.post(
            reverse("inventory:medicine_add"),
            {
                "name": "Amoxicillin",
                "category": "Antibiotic",
                "active_ingredient": "Amoxicillin",
                "dosage_form": "Capsule",
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

        self.assertRedirects(response, reverse("users:access_denied"))

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

        self.assertRedirects(response, reverse("users:access_denied"))

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
                "dosage_form": "Tablet",
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
