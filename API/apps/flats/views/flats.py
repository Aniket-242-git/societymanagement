"""DRF views for flats, wings, services and the flat-service audit trail."""
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from API.apps.core.permissions import IsAdmin, IsAdminOrCommittee
from API.apps.core.responses import api_error, api_success
from API.apps.flats.models import Flat, FlatServiceAuditLog, Service, Wing
from API.apps.flats.serializers import (
    FlatCreateSerializer, FlatDetailSerializer, FlatListSerializer,
    FlatServiceAuditLogSerializer, FlatServiceToggleSerializer,
    ServiceSerializer, WingSerializer,
)
from API.apps.flats.services import set_flat_service


class WingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrCommittee]
    serializer_class = WingSerializer

    def get_queryset(self):
        return Wing.objects.annotate(flat_count=Count("flats"))

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return api_success(data=data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Wing created successfully", data=ser.data, status=status.HTTP_201_CREATED)


class FlatViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrCommittee]
    filterset_fields = ["wing", "is_active"]

    def get_queryset(self):
        qs = Flat.objects.select_related("wing", "owner")
        wing = self.request.query_params.get("wing")
        active = self.request.query_params.get("is_active")
        search = self.request.query_params.get("search")
        if wing:
            qs = qs.filter(wing_id=wing)
        if active in ("true", "false"):
            qs = qs.filter(is_active=active == "true")
        if search:
            qs = qs.filter(owner_name__icontains=search)
        return qs.order_by("-created_at")

    def get_serializer_class(self):
        return FlatDetailSerializer if self.action == "retrieve" else (
            FlatCreateSerializer if self.action in ("create", "update", "partial_update")
            else FlatListSerializer
        )

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return api_success(data=self.get_serializer(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None, *args, **kwargs):
        try:
            obj = self.get_queryset().get(pk=pk)
        except Flat.DoesNotExist:
            return api_error("Flat not found", status=404)
        return api_success(data=self.get_serializer(obj).data)

    def create(self, request, *args, **kwargs):
        ser = FlatCreateSerializer(data=request.data)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Flat created successfully", data=ser.data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Flat.objects.get(pk=pk)
        except Flat.DoesNotExist:
            return api_error("Flat not found", status=404)
        ser = FlatCreateSerializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Flat updated successfully", data=ser.data)

    def destroy(self, request, pk=None, *args, **kwargs):
        """Soft-delete: deactivate instead of hard delete."""
        try:
            obj = Flat.objects.get(pk=pk)
        except Flat.DoesNotExist:
            return api_error("Flat not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return api_success("Flat deactivated successfully")

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser, JSONParser])
    def bulk_import(self, request):
        """Bulk import flats from an .xlsx file. Columns: wing, flat_no, floor, area, owner, maintenance."""
        file = request.FILES.get("file")
        if not file or not file.name.endswith((".xlsx", ".xls")):
            return api_error("Please upload a valid Excel (.xlsx) file in field 'file'.")
        try:
            from openpyxl import load_workbook
            wb = load_workbook(filename=file, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:  # noqa: BLE001
            return api_error(f"Could not read workbook: {e}")
        if not rows:
            return api_error("The spreadsheet is empty.")
        header = [str(c).strip().lower() if c else "" for c in rows[0]]
        idx = {name: header.index(name) for name in header if name}
        required = {"wing", "flat_no", "owner"}
        if not required.issubset(idx):
            return api_error(f"Missing required columns: {sorted(required - set(idx))}")
        created, skipped, wings = 0, 0, {}
        for row in rows[1:]:
            try:
                wname = str(row[idx["wing"]]).strip()
                fno = str(row[idx["flat_no"]]).strip()
                owner = str(row[idx["owner"]]).strip()
                if not wname or not fno:
                    skipped += 1
                    continue
                if wname not in wings:
                    wings[wname], _ = Wing.objects.get_or_create(name=wname)
                flat, was_new = Flat.objects.get_or_create(
                    wing=wings[wname], flat_no=fno,
                    defaults={
                        "owner_name": owner,
                        "floor": int(row[idx["floor"]] or 1) if "floor" in idx and row[idx["floor"]] else 1,
                        "area_sqft": row[idx["area"]] if "area" in idx else None,
                        "monthly_maintenance": row[idx["maintenance"]] if "maintenance" in idx and row[idx["maintenance"]] else 0,
                    },
                )
                created += 1 if was_new else 0
                skipped += 0 if was_new else 1
            except Exception:  # noqa: BLE001
                skipped += 1
        return api_success(f"Bulk import finished: {created} created, {skipped} skipped.")


class ServiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrCommittee]
    serializer_class = ServiceSerializer

    def get_queryset(self):
        return Service.objects.annotate(enabled_flat_count=Count("flat_links", filter=None)).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        return api_success(data=self.get_serializer(self.get_queryset(), many=True).data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Service created successfully", data=ser.data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Service.objects.get(pk=pk)
        except Service.DoesNotExist:
            return api_error("Service not found", status=404)
        ser = self.get_serializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Service updated successfully", data=ser.data)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            obj = Service.objects.get(pk=pk)
        except Service.DoesNotExist:
            return api_error("Service not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return api_success("Service deactivated successfully")


class FlatServiceViewSet(viewsets.ViewSet):
    """Assign/enable/disable a service per flat — every change writes an audit log."""

    permission_classes = [IsAdminOrCommittee]

    def list(self, request):
        qs = FlatServiceAuditLog.objects.select_related("flat", "service", "changed_by").all()
        flat = request.query_params.get("flat")
        if flat:
            qs = qs.filter(flat_id=flat)
        page = self.paginate_queryset(qs.order_by("-timestamp"))
        ser = FlatServiceAuditLogSerializer
        if page is not None:
            return self.get_paginated_response(ser(page, many=True).data)
        return api_success(data=ser(qs, many=True).data)

    def create(self, request):
        ser = FlatServiceToggleSerializer(data=request.data)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
        link = set_flat_service(
            ser.validated_data["flat"], ser.validated_data["service"],
            ser.validated_data["action"], request.user, ser.validated_data.get("remark", ""),
        )
        from API.apps.flats.serializers import FlatServiceSerializer
        return api_success(
            f"Service {ser.validated_data['action']}d for flat successfully",
            data=FlatServiceSerializer(link).data, status=201,
        )
