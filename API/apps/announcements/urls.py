from rest_framework.routers import DefaultRouter

from API.apps.announcements.views import AnnouncementViewSet

router = DefaultRouter()
router.register("announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = router.urls
