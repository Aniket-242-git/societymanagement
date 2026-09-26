from rest_framework.routers import DefaultRouter

from API.apps.flats.views import FlatServiceViewSet, FlatViewSet, ServiceViewSet, WingViewSet

router = DefaultRouter()
router.register("wings", WingViewSet, basename="wing")
router.register("flats", FlatViewSet, basename="flat")
router.register("services", ServiceViewSet, basename="service")
router.register("flat-services", FlatServiceViewSet, basename="flat-service")

urlpatterns = router.urls
