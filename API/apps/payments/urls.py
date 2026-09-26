from rest_framework.routers import DefaultRouter

from API.apps.payments.views import MaintenancePaymentViewSet

router = DefaultRouter()
router.register("payments", MaintenancePaymentViewSet, basename="payment")

urlpatterns = router.urls
