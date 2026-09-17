from rest_framework import serializers

from .models import Booking, Resource, Slot

ACTIVE_STATUSES = (Booking.Status.PENDING, Booking.Status.CONFIRMED)


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "name", "resource_type", "capacity"]


class SlotSerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Slot
        fields = ["id", "resource", "start_time", "end_time", "is_available"]

    def get_is_available(self, obj):
        return not obj.bookings.filter(status__in=ACTIVE_STATUSES).exists()


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["id", "slot", "customer_name", "customer_email", "status", "created_at"]
        read_only_fields = ["status", "created_at"]

    def validate_slot(self, slot):
        if Booking.objects.filter(slot=slot, status__in=ACTIVE_STATUSES).exists():
            raise serializers.ValidationError(
                "This slot already has an active booking (pending or confirmed)."
            )
        return slot
