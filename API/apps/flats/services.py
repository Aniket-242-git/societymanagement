"""Service-layer helpers for the flats app (keeps views thin, audit centralized)."""
from django.db import transaction

from API.apps.flats.models import FlatService, FlatServiceAuditLog


@transaction.atomic
def set_flat_service(flat, service, action, user, remark=""):
    """Enable/disable a service on a flat and write an audit log entry atomically."""
    obj, created = FlatService.objects.get_or_create(
        flat=flat, service=service,
        defaults={"status": "enabled" if action == "enable" else "disabled",
                  "changed_by": user, "remark": remark},
    )
    if not created:
        obj.status = "enabled" if action == "enable" else "disabled"
        obj.changed_by = user
        obj.remark = remark
        obj.save(update_fields=["status", "changed_by", "remark", "timestamp"])

    FlatServiceAuditLog.objects.create(
        flat=flat, service=service,
        action="create" if created else action,
        changed_by=user, remark=remark,
    )
    return obj
