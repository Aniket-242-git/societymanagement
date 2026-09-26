from rest_framework.routers import DefaultRouter

from API.apps.flats.views import (
    ExpenseCategoryViewSet, FlatServiceViewSet, FlatViewSet,
    ServiceViewSet, TenantViewSet, WingViewSet,
)

router = DefaultRouter()
router.register("wings", WingViewSet, basename="wing")
router.register("flats", FlatViewSet, basename="flat")
router.register("services", ServiceViewSet, basename="service")
router.register("flat-services", FlatServiceViewSet, basename="flat-service")
router.register("tenants", TenantViewSet, basename="tenant")
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")

urlpatterns = router.urls
