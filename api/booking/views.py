import os
import socket

from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, Resource, Slot
from .serializers import BookingSerializer, ResourceSerializer, SlotSerializer


class HealthCheckView(APIView):
    def get(self, request):
        return Response({"status": "ok", "version": os.environ.get("APP_VERSION", "dev"), "pod": socket.gethostname()})


class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer


class SlotViewSet(viewsets.ModelViewSet):
    queryset = Slot.objects.select_related("resource").prefetch_related("bookings").all()
    serializer_class = SlotSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        resource_id = self.request.query_params.get("resource")
        date_str = self.request.query_params.get("date")
        if resource_id:
            qs = qs.filter(resource_id=resource_id)
        if date_str:
            date = parse_date(date_str)
            if date:
                qs = qs.filter(start_time__date=date)
        return qs


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Booking.objects.select_related("slot").all()
    serializer_class = BookingSerializer

    @action(detail=True, methods=["patch"])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.status != Booking.Status.PENDING:
            return Response(
                {"detail": "Only pending bookings can be confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status"])
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status == Booking.Status.CANCELLED:
            return Response(
                {"detail": "Booking is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        return Response(self.get_serializer(booking).data)
