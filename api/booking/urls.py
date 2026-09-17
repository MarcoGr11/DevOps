from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, ResourceViewSet, SlotViewSet

router = DefaultRouter()
router.register("resources", ResourceViewSet, basename="resource")
router.register("slots", SlotViewSet, basename="slot")
router.register("bookings", BookingViewSet, basename="booking")

urlpatterns = router.urls
