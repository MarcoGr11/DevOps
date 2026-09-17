from django.test import TestCase
from django.utils import timezone

from booking.models import Booking, Resource, Slot
from booking.serializers import BookingSerializer, SlotSerializer


class BookingSerializerTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)
        self.slot = Slot.objects.create(
            resource=self.resource,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_valid_booking_passes_validation(self):
        serializer = BookingSerializer(data={
            "slot": self.slot.id,
            "customer_name": "John",
            "customer_email": "john@example.com",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_double_booking_on_active_status_rejected(self):
        Booking.objects.create(slot=self.slot, customer_name="John", customer_email="john@example.com")
        serializer = BookingSerializer(data={
            "slot": self.slot.id,
            "customer_name": "Jane",
            "customer_email": "jane@example.com",
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("slot", serializer.errors)

    def test_slot_with_only_cancelled_booking_can_be_rebooked(self):
        Booking.objects.create(
            slot=self.slot,
            customer_name="John",
            customer_email="john@example.com",
            status=Booking.Status.CANCELLED,
        )
        serializer = BookingSerializer(data={
            "slot": self.slot.id,
            "customer_name": "Jane",
            "customer_email": "jane@example.com",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)


class SlotSerializerTests(TestCase):
    def setUp(self):
        self.resource = Resource.objects.create(name="Room A", resource_type="room", capacity=4)
        self.slot = Slot.objects.create(
            resource=self.resource,
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
        )

    def test_is_available_true_without_bookings(self):
        data = SlotSerializer(self.slot).data
        self.assertTrue(data["is_available"])

    def test_is_available_false_with_active_booking(self):
        Booking.objects.create(slot=self.slot, customer_name="John", customer_email="john@example.com")
        data = SlotSerializer(self.slot).data
        self.assertFalse(data["is_available"])
