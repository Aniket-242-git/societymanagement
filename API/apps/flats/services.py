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


@transaction.atomic
def change_flat_owner(flat, new_user=None, new_owner_name="", reason="", user=None):
    """Transfer a flat to a new owner and record it in OwnerChangeHistory."""
    from API.apps.flats.models import FlatOwner, OwnerChangeHistory

    previous_name = flat.owner_name
    previous_user = flat.owner
    new_name = (new_owner_name or "").strip() or (
        (new_user.first_name or new_user.username) if new_user else previous_name
    )
    flat.owner = new_user
    flat.owner_name = new_name
    flat.save(update_fields=["owner", "owner_name", "updated_at"])

    if new_user is not None:
        FlatOwner.objects.update_or_create(
            flat=flat, user=new_user, defaults={"is_primary": True},
        )
    OwnerChangeHistory.objects.create(
        flat=flat,
        previous_owner_name=previous_name,
        new_owner_name=new_name,
        previous_user=previous_user,
        new_user=new_user,
        reason=reason,
        changed_by=user,
    )
    return flat
