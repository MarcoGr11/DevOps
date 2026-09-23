from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from booking.models import Resource, Slot


class HealthCheckTests(APITestCase):
    def test_health_check_returns_ok(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")


class ResourceApiTests(APITestCase):
    def test_crud_resource(self):
        create = self.client.post(
            "/api/resources/", {"name": "Room A", "resource_type": "room", "capacity": 4}
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        resource_id = create.data["id"]

        list_resp = self.client.get("/api/resources/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)

        update = self.client.patch(f"/api/resources/{resource_id}/", {"capacity": 6})
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data["capacity"], 6)

        delete = self.client.delete(f"/api/resources/{resource_id}/")
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)


class SlotApiTests(APITestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)
        self.slot = Slot.objects.create(
            resource=self.resource,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_list_slots_filtered_by_resource(self):
        other_resource = Resource.objects.create(name="Room B", resource_type="room", capacity=2)
        Slot.objects.create(
            resource=other_resource,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )
        response = self.client.get(f"/api/slots/?resource={self.resource.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_slots_filtered_by_date_excludes_other_days(self):
        other_day = timezone.now() + timezone.timedelta(days=5)
        Slot.objects.create(
            resource=self.resource, start_time=other_day, end_time=other_day + timezone.timedelta(hours=1)
        )
        today = timezone.now().date().isoformat()
        response = self.client.get(f"/api/slots/?date={today}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_slot_is_available_field(self):
        response = self.client.get(f"/api/slots/{self.slot.id}/")
        self.assertTrue(response.data["is_available"])


class BookingApiTests(APITestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)
        self.slot = Slot.objects.create(
            resource=self.resource,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def _create_booking(self, name="John", email="john@example.com"):
        return self.client.post(
            "/api/bookings/",
            {"slot": self.slot.id, "customer_name": name, "customer_email": email},
        )

    def test_create_booking_sets_status_pending(self):
        response = self._create_booking()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

    def test_double_booking_same_slot_returns_400(self):
        self._create_booking()
        response = self._create_booking(name="Jane", email="jane@example.com")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("slot", response.data)

    def test_confirm_booking(self):
        booking_id = self._create_booking().data["id"]
        response = self.client.patch(f"/api/bookings/{booking_id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")

    def test_confirm_already_confirmed_booking_returns_400(self):
        booking_id = self._create_booking().data["id"]
        self.client.patch(f"/api/bookings/{booking_id}/confirm/")
        response = self.client.patch(f"/api/bookings/{booking_id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_booking_frees_the_slot_for_rebooking(self):
        booking_id = self._create_booking().data["id"]
        cancel_resp = self.client.patch(f"/api/bookings/{booking_id}/cancel/")
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_resp.data["status"], "cancelled")

        slot_resp = self.client.get(f"/api/slots/{self.slot.id}/")
        self.assertTrue(slot_resp.data["is_available"])

        rebook_resp = self._create_booking(name="Jane", email="jane@example.com")
        self.assertEqual(rebook_resp.status_code, status.HTTP_201_CREATED)

    def test_cancel_already_cancelled_booking_returns_400(self):
        booking_id = self._create_booking().data["id"]
        self.client.patch(f"/api/bookings/{booking_id}/cancel/")
        response = self.client.patch(f"/api/bookings/{booking_id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
