from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from API.apps.core.permissions import IsAdminOrCommittee
from API.apps.core.exceptions import first_error_message
from API.apps.core.pagination import EnvelopePaginationMixin, StandardPagination
from API.apps.core.responses import api_error, api_success
from API.apps.payments.models import MaintenancePayment, PaymentAuditLog
from API.apps.payments.serializers import (
    PaymentApproveSerializer, PaymentAuditLogSerializer, PaymentCreateSerializer,
    PaymentDetailSerializer, PaymentEditSerializer, PaymentListSerializer,
    PaymentRejectSerializer,
)
from API.apps.payments.services import (
    approve_payment, delete_payment, edit_payment, reject_payment, submit_payment,
)


class MaintenancePaymentViewSet(EnvelopePaginationMixin, viewsets.ViewSet):
    """Maintenance fee approval workflow.

    Resident: submit + view own history.   Admin/committee: approve/reject/edit/soft-delete.
    Every mutation writes a PaymentAuditLog entry inside a DB transaction.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = StandardPagination

    def get_throttles(self):
        # rate-limit payment submissions via the scoped 'payment_submit' throttle
        if self.action == "submit":
            from rest_framework.throttling import ScopedRateThrottle
            throttle = ScopedRateThrottle()
            throttle.scope = "payment_submit"
            return [throttle]
        return super().get_throttles()

    def get_queryset(self, user=None):
        qs = (
            MaintenancePayment.objects.filter(is_deleted=False)
            .select_related("flat", "submitted_by", "approved_by")
            .order_by("-created_at")
        )
        user = user or self.request.user
        if not user.is_staff_role:
            from API.apps.flats.models import FlatOwner
            flat_ids = set(FlatOwner.objects.filter(user=user).values_list("flat_id", flat=True))
            qs = qs.filter(Q(flat__owner=user) | Q(flat_id__in=flat_ids))  # residents see all their flats
        status_f = self.request.query_params.get("status")
        if status_f:
            qs = qs.filter(status=status_f)
        flat = self.request.query_params.get("flat")
        if flat:
            qs = qs.filter(flat_id=flat)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(receipt_no__icontains=search) | Q(flat__flat_no__icontains=search)
                | Q(flat__owner_name__icontains=search) | Q(remark__icontains=search)
            )
        return qs

    # ---------------------------------------------------------------- CRUD
    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(PaymentListSerializer(page, many=True).data)
        return api_success(data=PaymentListSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            obj = self.get_queryset().get(pk=pk)
        except MaintenancePayment.DoesNotExist:
            return api_error("Payment not found", status=404)
        return api_success(data=PaymentDetailSerializer(obj).data)

    @action(detail=False, methods=["post"], throttle_classes=[ScopedRateThrottle])
    def submit(self, request):
        """Resident submits payment -> status pending (rate limited: payment_submit scope)."""
        ser = PaymentCreateSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        payment = submit_payment(ser.validated_data, request.user)
        return api_success("Payment submitted successfully and is pending approval",
                           data=PaymentDetailSerializer(payment).data, status=201)

    # ---------------------------------------------------------- admin actions
    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrCommittee])
    def approve(self, request, pk=None):
        try:
            payment = MaintenancePayment.objects.get(pk=pk, is_deleted=False)
        except MaintenancePayment.DoesNotExist:
            return api_error("Payment not found", status=404)
        if payment.status == "approved":
            return api_error("Payment is already approved.")
        ser = PaymentApproveSerializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        payment = approve_payment(payment, request.user, ser.validated_data.get("remark", ""))
        return api_success("Payment approved successfully", data=PaymentDetailSerializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminOrCommittee])
    def reject(self, request, pk=None):
        try:
            payment = MaintenancePayment.objects.get(pk=pk, is_deleted=False)
        except MaintenancePayment.DoesNotExist:
            return api_error("Payment not found", status=404)
        if payment.status == "approved":
            return api_error("Cannot reject an already approved payment. Edit it instead.")
        ser = PaymentRejectSerializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        payment = reject_payment(payment, request.user, ser.validated_data["reason"])
        return api_success("Payment rejected successfully", data=PaymentDetailSerializer(payment).data)

    def update(self, request, pk=None):
        """Admin edit — logs old & new values."""
        try:
            payment = MaintenancePayment.objects.get(pk=pk, is_deleted=False)
        except MaintenancePayment.DoesNotExist:
            return api_error("Payment not found", status=404)
        if not request.user.is_staff_role:
            return api_error("Only admin can edit payments.", status=403)
        ser = PaymentEditSerializer(data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        remark = request.data.get("audit_remark", "")
        payment = edit_payment(payment, ser.validated_data, request.user, remark)
        return api_success("Payment updated successfully", data=PaymentDetailSerializer(payment).data)

    def destroy(self, request, pk=None):
        """Soft-delete with audit trail — never hard delete."""
        try:
            payment = MaintenancePayment.objects.get(pk=pk, is_deleted=False)
        except MaintenancePayment.DoesNotExist:
            return api_error("Payment not found", status=404)
        if not request.user.is_staff_role:
            return api_error("Only admin can delete payments.", status=403)
        remark = request.data.get("remark", "") if hasattr(request, "data") else ""
        delete_payment(payment, request.user, remark)
        return api_success("Payment deleted successfully (soft delete)")

    # ---------------------------------------------------------- audit trail
    @action(detail=True, methods=["get"], permission_classes=[IsAdminOrCommittee])
    def audit_logs(self, request, pk=None):
        logs = PaymentAuditLog.objects.filter(payment_id=pk).select_related("admin").order_by("-timestamp")
        return api_success(data=PaymentAuditLogSerializer(logs, many=True).data)
