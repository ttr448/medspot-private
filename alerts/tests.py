from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alerts.models import Alert
from alerts.services import resolve_low_stock_alert, update_low_stock_alert
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy


User = get_user_model()


class LowStockAlertTests(TestCase):
    def setUp(self):
        self.pharmacist = User.objects.create_user(
            username="pharmacist1",
            password="test-password-123",
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
            dosage_form="Tablet",
        )
        self.inventory = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            quantity=10,
            minimum_threshold=5,
        )

    def test_alert_is_created_when_stock_reaches_threshold(self):
        self.inventory.quantity = 5
        self.inventory.save(update_fields=["quantity"])

        alert = update_low_stock_alert(
            self.inventory,
            self.pharmacist,
            previous_was_low=False,
        )

        self.assertEqual(Alert.objects.filter(pharmacy=self.pharmacy).count(), 1)
        self.assertFalse(alert.acknowledged)
        self.assertIn("5 available", alert.message)

    def test_no_alert_is_created_when_stock_is_above_threshold(self):
        update_low_stock_alert(
            self.inventory,
            self.pharmacist,
            previous_was_low=False,
        )

        self.assertFalse(Alert.objects.exists())

    def test_repeated_low_stock_updates_do_not_create_duplicates(self):
        self.inventory.quantity = 4
        self.inventory.save(update_fields=["quantity"])
        update_low_stock_alert(self.inventory, self.pharmacist, previous_was_low=False)

        self.inventory.quantity = 3
        self.inventory.save(update_fields=["quantity"])
        update_low_stock_alert(self.inventory, self.pharmacist, previous_was_low=True)

        self.assertEqual(Alert.objects.filter(pharmacy=self.pharmacy).count(), 1)

    def test_alert_is_closed_when_stock_recovers(self):
        self.inventory.quantity = 4
        self.inventory.save(update_fields=["quantity"])
        alert = update_low_stock_alert(
            self.inventory,
            self.pharmacist,
            previous_was_low=False,
        )

        self.inventory.quantity = 8
        self.inventory.save(update_fields=["quantity"])
        update_low_stock_alert(self.inventory, self.pharmacist, previous_was_low=True)

        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)
        self.assertIn("back above", alert.message)

    def test_existing_alert_is_reopened_when_stock_falls_low_again(self):
        self.inventory.quantity = 4
        self.inventory.save(update_fields=["quantity"])
        alert = update_low_stock_alert(
            self.inventory,
            self.pharmacist,
            previous_was_low=False,
        )

        self.inventory.quantity = 8
        self.inventory.save(update_fields=["quantity"])
        update_low_stock_alert(self.inventory, self.pharmacist, previous_was_low=True)

        self.inventory.quantity = 2
        self.inventory.save(update_fields=["quantity"])
        reopened_alert = update_low_stock_alert(
            self.inventory,
            self.pharmacist,
            previous_was_low=False,
        )

        self.assertEqual(Alert.objects.filter(pharmacy=self.pharmacy).count(), 1)
        self.assertEqual(reopened_alert.pk, alert.pk)
        self.assertFalse(reopened_alert.acknowledged)

    def test_pharmacist_can_dismiss_own_alert(self):
        alert = Alert.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            created_by=self.pharmacist,
            alert_type="low_stock",
            message="Panadol is low in stock.",
        )
        self.client.force_login(self.pharmacist)

        response = self.client.post(
            reverse("alerts:acknowledge", kwargs={"pk": alert.pk})
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)

    def test_pharmacist_cannot_dismiss_another_pharmacy_alert(self):
        other_pharmacist = User.objects.create_user(
            username="pharmacist2",
            password="test-password-123",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        other_pharmacy = Pharmacy.objects.create(
            name="Other Pharmacy",
            address="456 Side Street",
            owner=other_pharmacist,
        )
        alert = Alert.objects.create(
            pharmacy=other_pharmacy,
            medicine=self.medicine,
            alert_type="low_stock",
            message="Panadol is low in stock.",
        )
        self.client.force_login(self.pharmacist)

        response = self.client.post(
            reverse("alerts:acknowledge", kwargs={"pk": alert.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_alert_is_closed_when_medicine_is_removed(self):
        alert = Alert.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            alert_type="low_stock",
            message="Panadol is low in stock.",
        )

        resolve_low_stock_alert(self.inventory)

        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)
        self.assertIn("removed", alert.message)
