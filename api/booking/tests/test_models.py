from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from booking.models import Booking, Resource, Slot


class ResourceModelTests(TestCase):
    def test_str(self):
        resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)
        self.assertEqual(str(resource), "Room A")


class SlotModelTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)

    def test_unique_together_resource_start_time(self):
        start = timezone.now()
        end = start + timezone.timedelta(hours=1)
        Slot.objects.create(resource=self.resource, start_time=start, end_time=end)
        with self.assertRaises(IntegrityError):
            Slot.objects.create(resource=self.resource, start_time=start, end_time=end)


class BookingModelTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)
        self.slot = Slot.objects.create(
            resource=self.resource,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_default_status_is_pending(self):
        booking = Booking.objects.create(
            slot=self.slot, customer_name="John", customer_email="john@example.com"
        )
        self.assertEqual(booking.status, Booking.Status.PENDING)
