from django.db import models


class Resource(models.Model):
    class ResourceType(models.TextChoices):
        ROOM = "room", "Room"
        DESK = "desk", "Desk"

    name = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=10, choices=ResourceType.choices)
    capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Slot(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="slots")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        unique_together = ("resource", "start_time")
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.resource} @ {self.start_time}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    slot = models.ForeignKey(Slot, on_delete=models.CASCADE, related_name="bookings")
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - {self.slot} ({self.status})"
