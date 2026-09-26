"""DRF views for flats, wings, services and the flat-service audit trail."""
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from API.apps.core.permissions import IsAdmin, IsAdminOrCommittee
from API.apps.core.exceptions import first_error_message
from API.apps.core.pagination import EnvelopePaginationMixin, StandardPagination
from API.apps.core.responses import api_error, api_success
from API.apps.core.models import ExpenseCategory
from API.apps.flats.models import (
    Flat, FlatOwner, FlatServiceAuditLog, OwnerChangeHistory, Service, Tenant, Wing,
)
from API.apps.flats.serializers import (
    FlatCreateSerializer, FlatDetailSerializer, FlatListSerializer,
    FlatServiceAuditLogSerializer, FlatServiceToggleSerializer,
    OwnerChangeHistorySerializer, ServiceSerializer, TenantSerializer, WingSerializer,
)
from API.apps.flats.services import change_flat_owner, set_flat_service


class WingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # everyone logged-in can read the wing list (dropdowns); writes are admin-only
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminOrCommittee()]
    serializer_class = WingSerializer

    def get_queryset(self):
        return Wing.objects.annotate(flat_count=Count("flats"))

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return api_success(data=data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Wing created successfully", data=ser.data, status=status.HTTP_201_CREATED)


class FlatViewSet(EnvelopePaginationMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Read-only actions are allowed for every authenticated user; the
        per-flat history endpoints do their own ownership checks inside
        (_check_flat_access). All write actions stay admin/committee only."""
        if self.action in (
            "list", "retrieve", "history", "maintenance_history", "service_history",
            "owner_history", "tenants",
        ):
            return [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy",
                           "activate", "bulk_import"):
            return [IsAdminOrCommittee()]
        return [IsAdminOrCommittee()]

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
            from django.db.models import Q
            qs = qs.filter(
                Q(flat_no__icontains=search)
                | Q(owner_name__icontains=search)
                | Q(wing__name__icontains=search)
            )
        # ?mine=true -> only the flats mapped to the logged-in resident
        if self.request.query_params.get("mine") == "true":
            from API.apps.flats.models import FlatOwner
            flat_ids = set(
                FlatOwner.objects.filter(user=self.request.user).values_list("flat_id", flat=True)
            )
            qs = qs.filter(Q(pk__in=flat_ids) | Q(owner=self.request.user))
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
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Flat created successfully", data=ser.data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Flat.objects.get(pk=pk)
        except Flat.DoesNotExist:
            return api_error("Flat not found", status=404)
        ser = FlatCreateSerializer(obj, data=request.data, partial=True, context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Flat updated successfully", data=ser.data)

    def destroy(self, request, pk=None, *args, **kwargs):
        """Soft-delete: deactivate instead of hard delete.

        Blocked when residents are still mapped to the flat — revoke first.
        """
        try:
            obj = Flat.objects.get(pk=pk)
        except Flat.DoesNotExist:
            return api_error("Flat not found", status=404)
        if not obj.is_active:
            return api_success("Flat is already deactivated")
        from API.apps.flats.models import FlatOwner

        linked = list(FlatOwner.objects.filter(flat=obj).select_related("user")[:5])
        if linked or obj.owner_id:
            names = ", ".join(l.user.username for l in linked) or (obj.owner.username if obj.owner_id else "")
            return api_error(
                f"This flat is assigned to user(s): {names}. "
                "Revoke the flat from the user first (Users → Edit → Flats), then deactivate."
            )
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        return api_success("Flat deactivated successfully")

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrCommittee])
    def activate(self, request, pk=None):
        """Re-activate a previously deactivated flat."""
        try:
            obj = Flat.objects.get(pk=pk)
        except Flat.DoesNotExist:
            return api_error("Flat not found", status=404)
        if obj.is_active:
            return api_error("Flat is already active.")
        obj.is_active = True
        obj.save(update_fields=["is_active", "updated_at"])
        return api_success("Flat activated successfully", data=FlatDetailSerializer(obj).data)

    # ------------------------------------------------------------- history tabs
    def _check_flat_access(self, request, flat_id):
        """Return (flat, error_response). Residents may only access their own flats."""
        try:
            flat = Flat.objects.select_related("wing").get(pk=flat_id)
        except (Flat.DoesNotExist, TypeError, ValueError):
            return None, api_error("Flat not found", status=404)
        if not request.user.is_staff_role:
            allowed = FlatOwner.objects.filter(user=request.user, flat=flat).exists() or flat.owner_id == request.user.pk
            if not allowed:
                return None, api_error("You do not have access to this flat.", status=403)
        return flat, None

    @action(detail=False, methods=["get"])
    def maintenance_history(self, request):
        """Maintenance fee history of a flat since it was first assigned."""
        flat, err = self._check_flat_access(request, request.query_params.get("flat"))
        if err:
            return err
        from API.apps.payments.models import MaintenancePayment
        from API.apps.payments.serializers import PaymentListSerializer
        qs = (MaintenancePayment.objects.filter(flat=flat, is_deleted=False)
             .select_related("submitted_by", "approved_by").order_by("-created_at"))
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(PaymentListSerializer(page, many=True).data)
        return api_success(data=PaymentListSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"])
    def service_history(self, request):
        """Enable/disable audit trail of a flat."""
        flat, err = self._check_flat_access(request, request.query_params.get("flat"))
        if err:
            return err
        qs = (FlatServiceAuditLog.objects.filter(flat=flat)
              .select_related("service", "changed_by").order_by("-timestamp"))
        page = self.paginate_queryset(qs)
        ser = FlatServiceAuditLogSerializer
        if page is not None:
            return self.get_paginated_response(ser(page, many=True).data)
        return api_success(data=ser(qs, many=True).data)

    @action(detail=False, methods=["get", "post"], permission_classes=[IsAuthenticated])
    def tenants(self, request):
        """Tenant history of a flat (GET list / POST add — admin only for write)."""
        flat, err = self._check_flat_access(request, request.query_params.get("flat") or request.data.get("flat"))
        if err:
            return err
        if request.method == "GET":
            qs = Tenant.objects.filter(flat=flat).select_related("added_by")
            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(TenantSerializer(page, many=True).data)
            return api_success(data=TenantSerializer(qs, many=True).data)
        if not request.user.is_staff_role:
            return api_error("Only admin can add tenants.", status=403)
        ser = TenantSerializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save(added_by=request.user, flat=flat)
        return api_success("Tenant added successfully", data=ser.data, status=201)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """FLAT HISTORY (combined) — powers the History modal on BOTH the admin
        Flats page and the Resident dashboard in one round-trip.

        Returns maintenance-fee history, tenant history, owner-change history
        and service enable/disable audit trail for this flat — since it was
        first assigned. Residents can only open it for their own flats
        (_check_flat_access); admins/committee see every flat.
        """
        flat, err = self._check_flat_access(request, pk)
        if err:
            return err

        from API.apps.payments.models import MaintenancePayment
        from API.apps.payments.serializers import PaymentListSerializer

        payments = (MaintenancePayment.objects
                    .filter(flat=flat, is_deleted=False)
                    .select_related("submitted_by", "approved_by")
                    .order_by("-created_at")[:100])
        tenants = (Tenant.objects.filter(flat=flat)
                   .select_related("added_by").order_by("-move_in_date", "-created_at")[:100])
        owners = (OwnerChangeHistory.objects.filter(flat=flat)
                  .select_related("changed_by").order_by("-changed_at")[:100])
        services = (FlatServiceAuditLog.objects.filter(flat=flat)
                    .select_related("service", "changed_by").order_by("-timestamp")[:100])

        return api_success(data={
            "flat": FlatListSerializer(flat).data,
            "maintenance": PaymentListSerializer(payments, many=True).data,
            "tenants": TenantSerializer(tenants, many=True).data,
            "owner_changes": OwnerChangeHistorySerializer(owners, many=True).data,
            "services": FlatServiceAuditLogSerializer(services, many=True).data,
        })

    @action(detail=False, methods=["get", "post"], permission_classes=[IsAuthenticated])
    def owner_history(self, request):
        """Owner-change history (GET) and owner transfer (POST — admin only)."""
        flat, err = self._check_flat_access(request, request.query_params.get("flat") or request.data.get("flat"))
        if err:
            return err
        if request.method == "GET":
            qs = OwnerChangeHistory.objects.filter(flat=flat).select_related("changed_by")
            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(OwnerChangeHistorySerializer(page, many=True).data)
            return api_success(data=OwnerChangeHistorySerializer(qs, many=True).data)
        if not request.user.is_staff_role:
            return api_error("Only admin can transfer flat ownership.", status=403)
        new_user_id = request.data.get("new_user")
        new_name = (request.data.get("new_owner_name") or "").strip()
        if not new_user_id and not new_name:
            return api_error("Provide new_user (id) or new_owner_name to transfer the flat.")
        new_user = None
        if new_user_id:
            from API.apps.accounts.models import User
            try:
                new_user = User.objects.get(pk=new_user_id)
            except User.DoesNotExist:
                return api_error("Selected user not found.", status=404)
        flat = change_flat_owner(
            flat, new_user=new_user, new_owner_name=new_name,
            reason=(request.data.get("reason") or "").strip(), user=request.user,
        )
        return api_success("Flat ownership transferred successfully",
                           data=FlatDetailSerializer(flat).data)

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
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # residents need the master service list for their "services active" view
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminOrCommittee()]

    serializer_class = ServiceSerializer

    def get_queryset(self):
        qs = Service.objects.all()
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        return api_success(data=self.get_serializer(self.get_queryset(), many=True).data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Service created successfully", data=ser.data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Service.objects.get(pk=pk)
        except Service.DoesNotExist:
            return api_error("Service not found", status=404)
        ser = self.get_serializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
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


class FlatServiceViewSet(EnvelopePaginationMixin, viewsets.ViewSet):
    """Assign/enable/disable a service per flat — every change writes an audit log."""

    permission_classes = [IsAdminOrCommittee]
    pagination_class = StandardPagination

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
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        link = set_flat_service(
            ser.validated_data["flat"], ser.validated_data["service"],
            ser.validated_data["action"], request.user, ser.validated_data.get("remark", ""),
        )
        from API.apps.flats.serializers import FlatServiceSerializer
        return api_success(
            f"Service {ser.validated_data['action']}d for flat successfully",
            data=FlatServiceSerializer(link).data, status=201,
        )


class TenantViewSet(viewsets.ModelViewSet):
    """CRUD over tenant records (admin/committee)."""

    permission_classes = [IsAdminOrCommittee]
    serializer_class = TenantSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Tenant.objects.select_related("flat", "flat__wing", "added_by")
        flat = self.request.query_params.get("flat")
        if flat:
            qs = qs.filter(flat_id=flat)
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=search) | Q(phone__icontains=search))
        return qs.order_by("-move_in_date", "-created_at")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return api_success(data=self.get_serializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save(added_by=request.user)
        return api_success("Tenant added successfully", data=ser.data, status=201)

    def update(self, request, *args, **kwargs):
        ser = self.get_serializer(self.get_object(), data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Tenant updated successfully", data=ser.data)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.status = "vacated"
        from datetime import date
        if not obj.move_out_date:
            obj.move_out_date = date.today()
        obj.save(update_fields=["status", "move_out_date", "updated_at"])
        return api_success("Tenant marked as vacated")


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """Settings tab: manage expense categories (visible to all authenticated users)."""

    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = ExpenseCategory.objects.all()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs.order_by("name")

    def get_serializer_class(self):
        from rest_framework import serializers as drf_serializers

        class _ExpenseCategorySerializer(drf_serializers.ModelSerializer):
            class Meta:
                model = ExpenseCategory
                fields = ["id", "name", "is_active", "created_at"]
        return _ExpenseCategorySerializer

    def list(self, request, *args, **kwargs):
        ser = self.get_serializer(self.get_queryset(), many=True)
        return api_success(data=ser.data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            msg = "This expense category already exists." if ExpenseCategory.objects.filter(
                name__iexact=request.data.get("name", "")).exists() else first_error_message(ser.errors)
            return api_error(msg, errors=ser.errors)
        ser.save()
        return api_success("Expense category created successfully", data=ser.data, status=201)

    def update(self, request, *args, **kwargs):
        try:
            obj = ExpenseCategory.objects.get(pk=kwargs.get("pk"))
        except ExpenseCategory.DoesNotExist:
            return api_error("Expense category not found", status=404)
        ser = self.get_serializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Expense category updated successfully", data=ser.data)

    def destroy(self, request, *args, **kwargs):
        try:
            obj = ExpenseCategory.objects.get(pk=kwargs.get("pk"))
        except ExpenseCategory.DoesNotExist:
            return api_error("Expense category not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return api_success("Expense category deactivated successfully")
