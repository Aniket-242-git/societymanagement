from rest_framework.routers import DefaultRouter

from API.apps.issues.views import IssueViewSet

router = DefaultRouter()
router.register("issues", IssueViewSet, basename="issue")

urlpatterns = router.urls
