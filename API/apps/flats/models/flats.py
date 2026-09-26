from django.conf import settings
from django.db import models


class Wing(models.Model):
    """Block / wing of the society."""

    name = models.CharField(max_length=20, unique=True)  # e.g. "A", "B"
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"Wing {self.name}"


class Flat(models.Model):
    wing = models.ForeignKey(Wing, on_delete=models.PROTECT, related_name="flats")
    flat_no = models.CharField(max_length=20)
    floor = models.PositiveSmallIntegerField(default=1)
    area_sqft = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    owner_name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_flats",
        limit_choices_to={"role": "resident"},
    )
    is_tenant_occupied = models.BooleanField(default=False, help_text="True if occupied by tenant, else owner")
    monthly_maintenance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["wing__name", "floor", "flat_no"]
        unique_together = ("wing", "flat_no")
        indexes = [models.Index(fields=["is_active"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return f"{self.wing.name}-{self.flat_no} ({self.owner_name})" if self.wing_id else f"{self.flat_no} ({self.owner_name})"


class FlatOwner(models.Model):
    """Many-to-many between users and flats (a resident CAN own multiple flats).

    The legacy `Flat.owner` FK is kept in sync with the *primary* owner so all
    existing queries (`flat__owner=user`, dashboard scoping, etc.) keep working.
    """

    flat = models.ForeignKey(Flat, on_delete=models.CASCADE, related_name="owner_links")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="flat_links"
    )
    is_primary = models.BooleanField(default=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("flat", "user")
        verbose_name_plural = "Flat owners"
        ordering = ["-is_primary", "added_at"]

    def __str__(self):
        return f"{self.user.username} @ {self.flat}"


class Service(models.Model):
    """Master list of utility services (Water, Electricity, Parking...)."""

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=250, blank=True)
    monthly_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FlatService(models.Model):
    """Per-flat service enable/disable with full audit trail."""

    STATUS_CHOICES = [("enabled", "Enabled"), ("disabled", "Disabled")]

    flat = models.ForeignKey(Flat, on_delete=models.CASCADE, related_name="services")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="flat_links")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="enabled", db_index=True)
    remark = models.CharField(max_length=250, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="service_changes"
    )
    timestamp = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        unique_together = ("flat", "service")
        verbose_name_plural = "Flat services"
        indexes = [models.Index(fields=["flat", "status"])]

    def __str__(self):
        return f"{self.flat} - {self.service} [{self.status}]"


class FlatServiceAuditLog(models.Model):
    """Immutable audit entry for every flat-service action."""

    ACTION_CHOICES = [("enable", "Enable"), ("disable", "Disable"), ("create", "Create"), ("update", "Update")]

    flat = models.ForeignKey(Flat, on_delete=models.CASCADE, related_name="service_audit_logs")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    remark = models.CharField(max_length=250, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Flat service audit logs"

    def __str__(self):
        return f"{self.action}: {self.flat} / {self.service} by {self.changed_by}"
