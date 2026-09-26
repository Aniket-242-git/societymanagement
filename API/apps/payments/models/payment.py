from django.conf import settings
from django.db import models

from API.apps.flats.models import Flat


class MaintenancePayment(models.Model):
    """Resident-submitted maintenance payment awaiting admin approval."""

    STATUS_CHOICES = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    MODE_CHOICES = [
        ("cash", "Cash"), ("upi", "UPI"), ("cheque", "Cheque"),
        ("netbanking", "Net Banking"), ("card", "Card"), ("other", "Other"),
    ]

    flat = models.ForeignKey(Flat, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_no = models.CharField(max_length=50, blank=True)
    mode = models.CharField(max_length=15, choices=MODE_CHOICES, default="cash")
    remark = models.CharField(max_length=250, blank=True)
    proof_image = models.ImageField(upload_to="payments/proofs/", blank=True, null=True)
    period_month = models.PositiveSmallIntegerField(default=1, help_text="Month (1-12) this payment is for")
    period_year = models.PositiveSmallIntegerField(default=2026, help_text="Year this payment is for")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="payments_submitted"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments_approved"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=250, blank=True)
    is_deleted = models.BooleanField(default=False, help_text="Soft-delete flag; never hard-delete.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["flat", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]
        verbose_name_plural = "Maintenance payments"

    def __str__(self):
        return f"{self.flat} - ₹{self.amount} [{self.status}]"


class PaymentAuditLog(models.Model):
    """Every create/edit/approve/reject/delete of a payment is recorded here."""

    ACTION_CHOICES = [
        ("submit", "Submitted"), ("approve", "Approved"), ("reject", "Rejected"),
        ("edit", "Edited"), ("delete", "Deleted"),
    ]

    payment = models.ForeignKey(MaintenancePayment, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="payment_audit_actions"
    )
    remark = models.CharField(max_length=250, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Payment audit logs"

    def __str__(self):
        return f"{self.action} #{self.payment_id} by {self.admin}"
