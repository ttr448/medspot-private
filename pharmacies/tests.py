from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alerts.models import Alert
from inventory.models import Inventory, InventoryLog
from medicines.models import Medicine
from pharmacies.models import Pharmacy


User = get_user_model()


class PharmacistDashboardTests(TestCase):
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
            strength="500 mg",
        )
        self.own_inventory = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            quantity=4,
            minimum_threshold=5,
        )
        self.own_alert = Alert.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            alert_type="low_stock",
            message="Panadol is low in stock.",
        )
        self.dashboard_url = reverse("pharmacies:dashboard")
        self.client.force_login(self.pharmacist)

    def test_verified_pharmacist_sees_own_inventory_and_low_stock_alerts(self):
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
        other_medicine = Medicine.objects.create(name="Ibuprofen")
        other_inventory = Inventory.objects.create(
            pharmacy=other_pharmacy,
            medicine=other_medicine,
            quantity=10,
            minimum_threshold=2,
        )
        other_alert = Alert.objects.create(
            pharmacy=other_pharmacy,
            medicine=other_medicine,
            alert_type="low_stock",
            message="Ibuprofen is low in stock.",
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["inventory_items"]), [self.own_inventory])
        self.assertEqual(list(response.context["low_stock_alerts"]), [self.own_alert])
        self.assertNotContains(response, "Other Pharmacy")
        self.assertNotIn(other_inventory, response.context["inventory_items"])
        self.assertNotIn(other_alert, response.context["low_stock_alerts"])

    def test_acknowledged_alert_is_not_shown_on_dashboard(self):
        self.own_alert.acknowledged = True
        self.own_alert.save(update_fields=["acknowledged"])

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["low_stock_alerts"])

    def test_verified_pharmacist_without_a_pharmacy_sees_helpful_message(self):
        user_without_pharmacy = User.objects.create_user(
            username="no_pharmacy",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(user_without_pharmacy)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pharmacy is linked to your account yet.")

    def test_patient_cannot_access_pharmacist_dashboard(self):
        patient = User.objects.create_user(
            username="patient1",
            password="Strong-Test-Password-2026!",
            role="patient",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(patient)

        response = self.client.get(self.dashboard_url)

        self.assertRedirects(
            response,
            reverse("users:access_denied"),
            target_status_code=403,
        )

    def test_unverified_pharmacist_cannot_access_dashboard(self):
        unverified = User.objects.create_user(
            username="pending_pharmacist",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=False,
        )
        self.client.force_login(unverified)

        response = self.client.get(self.dashboard_url)

        self.assertRedirects(
            response,
            reverse("users:access_denied"),
            target_status_code=403,
        )

    def test_pharmacist_can_update_own_pharmacy_working_hours(self):
        response = self.client.post(
            self.dashboard_url,
            {
                "save_working_hours": "1",
                "working_hours": "Sat-Thu 08:00-22:00; Fri 16:00-22:00",
            },
        )

        self.assertRedirects(response, self.dashboard_url)
        self.pharmacy.refresh_from_db()
        self.assertEqual(
            self.pharmacy.working_hours,
            "Sat-Thu 08:00-22:00; Fri 16:00-22:00",
        )

    def test_dashboard_displays_only_its_pharmacy_inventory_history(self):
        own_log = InventoryLog.objects.create(
            source_inventory_id_snapshot=self.own_inventory.pk,
            pharmacy_id_snapshot=self.pharmacy.pk,
            pharmacy_name=self.pharmacy.name,
            medicine_id_snapshot=self.medicine.pk,
            medicine_name=self.medicine.name,
            actor_id_snapshot=self.pharmacist.pk,
            actor_username=self.pharmacist.username,
            action="update",
            changes=[{"field": "Quantity", "before": 20, "after": 4}],
        )

        other_user = User.objects.create_user(
            username="other_history_pharmacist",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        other_log = InventoryLog.objects.create(
            source_inventory_id_snapshot=98765,
            pharmacy_id_snapshot=98765,
            pharmacy_name="Other Pharmacy",
            medicine_id_snapshot=98765,
            medicine_name="Other Medicine",
            actor_id_snapshot=other_user.pk,
            actor_username=other_user.username,
            action="delete",
            changes=[],
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["inventory_logs"]), [own_log])
        self.assertContains(response, "Inventory update history")
        self.assertContains(response, "Quantity")
        self.assertNotContains(response, "Other Medicine")
        self.assertNotIn(other_log, response.context["inventory_logs"])

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(self.dashboard_url)

        self.assertRedirects(response, reverse("users:login"))
