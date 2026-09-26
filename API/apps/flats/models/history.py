from django.db import models

from API.apps.flats.models import Flat


class Tenant(models.Model):
    """Tenant occupying a flat (tenant history per flat)."""

    STATUS_CHOICES = [("active", "Active"), ("vacated", "Vacated")]

    flat = models.ForeignKey(Flat, on_delete=models.PROTECT, related_name="tenants")
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True)
    id_proof_type = models.CharField(max_length=30, blank=True, help_text="Aadhaar / Passport / DL etc.")
    id_proof_no = models.CharField(max_length=40, blank=True)
    move_in_date = models.DateField()
    move_out_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)
    remark = models.CharField(max_length=250, blank=True)
    added_by = models.ForeignKey(
        "accounts.User", null=True, on_delete=models.SET_NULL, related_name="tenants_added"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-move_in_date", "-created_at"]
        indexes = [models.Index(fields=["flat", "status"])]

    def __str__(self):
        return f"{self.name} @ {self.flat} [{self.status}]"


class OwnerChangeHistory(models.Model):
    """Immutable record of every owner/occupancy change on a flat."""

    flat = models.ForeignKey(Flat, on_delete=models.CASCADE, related_name="owner_history")
    previous_owner_name = models.CharField(max_length=100, blank=True)
    new_owner_name = models.CharField(max_length=100)
    previous_user = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="owner_changes_before",
    )
    new_user = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="owner_changes_after",
    )
    reason = models.CharField(max_length=250, blank=True, help_text="e.g. Sale deed, transfer, gift")
    changed_by = models.ForeignKey(
        "accounts.User", null=True, on_delete=models.SET_NULL, related_name="owner_changes_logged"
    )
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name_plural = "Owner change history"

    def __str__(self):
        return f"{self.flat}: {self.previous_owner_name or '-'} -> {self.new_owner_name}"
