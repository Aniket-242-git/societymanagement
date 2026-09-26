from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from API.apps.announcements.models import Announcement
from API.apps.announcements.serializers import AnnouncementSerializer
from API.apps.core.permissions import IsAdminOrCommittee
from API.apps.core.responses import api_error, api_success


class AnnouncementViewSet(viewsets.ModelViewSet):
    """All authenticated users can read; admin/committee can write."""

    serializer_class = AnnouncementSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminOrCommittee()]

    def get_queryset(self):
        qs = Announcement.objects.filter(is_active=True).select_related("created_by")
        # hide expired announcements from residents
        if not (self.request.user.is_staff_role):
            qs = qs.filter(models_expiry_none_or_future())
        return qs.order_by("-pinned", "-created_at")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        ser = self.get_serializer
        if page is not None:
            return self.get_paginated_response(ser(page, many=True).data)
        return api_success(data=ser(self.get_queryset(), many=True).data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save(created_by=request.user)
        return api_success("Announcement published successfully", data=ser.data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Announcement.objects.get(pk=pk, is_active=True)
        except Announcement.DoesNotExist:
            return api_error("Announcement not found", status=404)
        ser = self.get_serializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Announcement updated successfully", data=ser.data)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            obj = Announcement.objects.get(pk=pk, is_active=True)
        except Announcement.DoesNotExist:
            return api_error("Announcement not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return api_success("Announcement deleted successfully")


def models_expiry_none_or_future():
    from django.db.models import Q
    return Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.now().date())
