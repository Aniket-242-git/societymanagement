"""Service layer for the maintenance payment approval workflow.

All multi-step writes are wrapped in transaction.atomic() and every
mutation appends an immutable PaymentAuditLog entry (never hard-delete).
"""
from django.db import transaction
from django.utils import timezone

from API.apps.payments.models import MaintenancePayment, PaymentAuditLog


def _snapshot(payment):
    return {
        "amount": str(payment.amount),
        "receipt_no": payment.receipt_no,
        "mode": payment.mode,
        "remark": payment.remark,
        "status": payment.status,
        "period_month": payment.period_month,
        "period_year": payment.period_year,
    }


@transaction.atomic
def submit_payment(validated_data, user):
    payment = MaintenancePayment.objects.create(**validated_data, submitted_by=user, status="pending")
    PaymentAuditLog.objects.create(
        payment=payment, action="submit", old_value=None,
        new_value=_snapshot(payment), admin=user, remark="Payment submitted by resident",
    )
    return payment


@transaction.atomic
def approve_payment(payment, admin, remark=""):
    old = _snapshot(payment)
    payment.status = "approved"
    payment.approved_by = admin
    payment.approved_at = timezone.now()
    payment.rejection_reason = ""
    payment.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason", "updated_at"])
    PaymentAuditLog.objects.create(
        payment=payment, action="approve", old_value=old,
        new_value=_snapshot(payment), admin=admin, remark=remark or "Approved",
    )
    return payment


@transaction.atomic
def reject_payment(payment, admin, reason=""):
    old = _snapshot(payment)
    payment.status = "rejected"
    payment.approved_by = admin
    payment.approved_at = timezone.now()
    payment.rejection_reason = reason
    payment.save(update_fields=["status", "approved_by", "approved_at", "rejection_reason", "updated_at"])
    PaymentAuditLog.objects.create(
        payment=payment, action="reject", old_value=old,
        new_value=_snapshot(payment), admin=admin, remark=reason or "Rejected",
    )
    return payment


@transaction.atomic
def edit_payment(payment, validated_data, admin, remark=""):
    old = _snapshot(payment)
    for field, value in validated_data.items():
        setattr(payment, field, value)
    payment.save(update_fields=[*validated_data.keys(), "updated_at"])
    PaymentAuditLog.objects.create(
        payment=payment, action="edit", old_value=old,
        new_value=_snapshot(payment), admin=admin, remark=remark,
    )
    return payment


@transaction.atomic
def delete_payment(payment, admin, remark=""):
    """Soft delete only — record keeps existing with audit trail."""
    old = _snapshot(payment)
    payment.is_deleted = True
    payment.save(update_fields=["is_deleted", "updated_at"])
    PaymentAuditLog.objects.create(
        payment=payment, action="delete", old_value=old,
        new_value=None, admin=admin, remark=remark or "Soft deleted",
    )
    return payment
