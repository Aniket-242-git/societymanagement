import os

from django.conf import settings as dj_settings
from rest_framework import serializers

from API.apps.flats.models import Flat
from API.apps.payments.models import MaintenancePayment, PaymentAuditLog


# ------------------------------------------------------------------ submit
class PaymentCreateSerializer(serializers.ModelSerializer):
    """Resident submits payment -> pending approval."""

    class Meta:
        model = MaintenancePayment
        fields = ["flat", "amount", "receipt_no", "mode", "remark",
                  "proof_image", "period_month", "period_year"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_proof_image(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in dj_settings.ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError(f"Unsupported image type {ext}.")
        if value.size > dj_settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError("Proof image exceeds 5MB limit.")
        return value

    def validate_flat(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Flat is inactive.")
        request = self.context.get("request")
        if request and not request.user.is_staff_role and value.owner_id != request.user.id:
            raise serializers.ValidationError("You can submit payments only for your own flat.")
        return value


# ------------------------------------------------------------------ list / detail
MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


class PaymentListSerializer(serializers.ModelSerializer):
    flat_label = serializers.CharField(source="flat.__str__", read_only=True)
    submitted_by_name = serializers.CharField(source="submitted_by.username", read_only=True, default=None)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    # UI shows the month NAME (e.g. "Sep 2026") instead of a raw period number
    month_display = serializers.SerializerMethodField()

    class Meta:
        model = MaintenancePayment
        fields = [
            "id", "flat", "flat_label", "amount", "receipt_no", "mode", "mode_display",
            "remark", "proof_image", "period_month", "period_year", "month_display",
            "status", "status_display",
            "submitted_by", "submitted_by_name", "approved_by", "approved_by_name",
            "approved_at", "rejection_reason", "created_at",
        ]

    def get_month_display(self, obj):
        m = obj.period_month or 0
        name = MONTH_NAMES[m] if 1 <= m <= 12 else ""
        return f"{name[:3]} {obj.period_year}".strip() if name else str(obj.period_year or "")


class PaymentDetailSerializer(PaymentListSerializer):
    audit_logs = serializers.SerializerMethodField()

    class Meta(PaymentListSerializer.Meta):
        fields = PaymentListSerializer.Meta.fields + ["audit_logs"]

    def get_audit_logs(self, obj):
        return PaymentAuditLogSerializer(obj.audit_logs.select_related("admin").all(), many=True).data


# ------------------------------------------------------------------ approve / reject
class PaymentApproveSerializer(serializers.Serializer):
    """Separate serializer per action."""

    remark = serializers.CharField(required=False, allow_blank=True, max_length=250)


class PaymentRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=250)


class PaymentEditSerializer(serializers.ModelSerializer):
    """Admin edit of an existing payment (any status)."""

    class Meta:
        model = MaintenancePayment
        fields = ["amount", "receipt_no", "mode", "remark", "period_month", "period_year", "status"]


class PaymentAuditLogSerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source="admin.username", read_only=True, default=None)

    class Meta:
        model = PaymentAuditLog
        fields = ["id", "payment", "action", "old_value", "new_value",
                  "admin", "admin_name", "remark", "timestamp"]
