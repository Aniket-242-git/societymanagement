from rest_framework import serializers

from API.apps.flats.models import (
    Flat, FlatService, FlatServiceAuditLog, OwnerChangeHistory, Service, Tenant, Wing,
)


# ------------------------------------------------------------------ Wing
class WingSerializer(serializers.ModelSerializer):
    flat_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Wing
        fields = ["id", "name", "description", "flat_count", "created_at"]


# ------------------------------------------------------------------ Flat
class FlatListSerializer(serializers.ModelSerializer):
    wing_name = serializers.CharField(source="wing.name", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True, default=None)
    flat_label = serializers.SerializerMethodField()

    class Meta:
        model = Flat
        fields = [
            "id", "wing", "wing_name", "flat_no", "floor", "area_sqft",
            "owner_name", "owner", "owner_username", "is_tenant_occupied",
            "monthly_maintenance", "is_active", "created_at", "flat_label",
        ]

    def get_flat_label(self, obj):
        return f"{obj.wing.name}-{obj.flat_no}" if obj.wing_id else obj.flat_no


class FlatCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flat
        fields = [
            "wing", "flat_no", "floor", "area_sqft", "owner_name",
            "owner", "is_tenant_occupied", "monthly_maintenance", "is_active",
        ]

    def update(self, instance, validated_data):
        """Log an OwnerChangeHistory entry whenever the owner changes."""
        new_owner = validated_data.get("owner")
        new_owner_name = validated_data.get("owner_name")
        owner_changed = (
            "owner" in validated_data and validated_data["owner"] != instance.owner
        ) or (
            "owner_name" in validated_data
            and validated_data["owner_name"].strip().lower() != instance.owner_name.strip().lower()
        )
        request = self.context.get("request")
        if owner_changed:
            from API.apps.flats.models import OwnerChangeHistory

            OwnerChangeHistory.objects.create(
                flat=instance,
                previous_owner_name=instance.owner_name,
                new_owner_name=new_owner_name or (new_owner.first_name or new_owner.username if new_owner else instance.owner_name),
                previous_user=instance.owner,
                new_user=new_owner if "owner" in validated_data else instance.owner,
                reason=validated_data.pop("change_reason", "") or "",
                changed_by=getattr(request, "user", None),
            )
        return super().update(instance, validated_data)


class FlatDetailSerializer(FlatListSerializer):
    services = serializers.SerializerMethodField()

    class Meta(FlatListSerializer.Meta):
        fields = FlatListSerializer.Meta.fields + ["services", "updated_at"]

    def get_services(self, obj):
        return FlatServiceSerializer(obj.services.select_related("service").filter(status="enabled"), many=True).data


# ------------------------------------------------------------------ Service
class ServiceSerializer(serializers.ModelSerializer):
    enabled_flat_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Service
        fields = ["id", "name", "description", "monthly_charges", "is_active", "enabled_flat_count", "created_at"]


# ------------------------------------------------------------------ FlatService
class FlatServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    flat_label = serializers.CharField(source="flat.__str__", read_only=True)

    class Meta:
        model = FlatService
        fields = ["id", "flat", "flat_label", "service", "service_name",
                  "status", "remark", "changed_by", "timestamp"]
        read_only_fields = ["changed_by", "timestamp"]


class FlatServiceToggleSerializer(serializers.Serializer):
    """Separate serializer per action: enable/disable a service on a flat."""

    flat = serializers.PrimaryKeyRelatedField(queryset=Flat.objects.filter(is_active=True))
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    action = serializers.ChoiceField(choices=["enable", "disable"])
    remark = serializers.CharField(required=False, allow_blank=True, max_length=250)


# ------------------------------------------------------------------ Audit
class FlatServiceAuditLogSerializer(serializers.ModelSerializer):
    flat_label = serializers.CharField(source="flat.__str__", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    changed_by_name = serializers.CharField(source="changed_by.username", read_only=True, default=None)

    class Meta:
        model = FlatServiceAuditLog
        fields = ["id", "flat", "flat_label", "service", "service_name",
                  "action", "changed_by", "changed_by_name", "remark", "timestamp"]


# ------------------------------------------------------------------ Tenant / Owner history
class TenantSerializer(serializers.ModelSerializer):
    flat_label = serializers.SerializerMethodField()
    added_by_name = serializers.CharField(source="added_by.username", read_only=True, default=None)

    class Meta:
        model = Tenant
        fields = [
            "id", "flat", "flat_label", "name", "phone", "id_proof_type", "id_proof_no",
            "move_in_date", "move_out_date", "status", "remark",
            "added_by", "added_by_name", "created_at",
        ]
        read_only_fields = ["added_by", "created_at"]

    def get_flat_label(self, obj):
        return f"{obj.flat.wing.name}-{obj.flat.flat_no}" if obj.flat.wing_id else obj.flat.flat_no


class OwnerChangeHistorySerializer(serializers.ModelSerializer):
    flat_label = serializers.SerializerMethodField()
    changed_by_name = serializers.CharField(source="changed_by.username", read_only=True, default=None)

    class Meta:
        model = OwnerChangeHistory
        fields = [
            "id", "flat", "flat_label", "previous_owner_name", "new_owner_name",
            "previous_user", "new_user", "reason", "changed_by", "changed_by_name", "changed_at",
        ]

    def get_flat_label(self, obj):
        return f"{obj.flat.wing.name}-{obj.flat.flat_no}" if obj.flat.wing_id else obj.flat.flat_no
