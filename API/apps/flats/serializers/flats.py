from rest_framework import serializers

from API.apps.flats.models import (
    Flat, FlatService, FlatServiceAuditLog, Service, Wing,
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

    class Meta:
        model = Flat
        fields = [
            "id", "wing", "wing_name", "flat_no", "floor", "area_sqft",
            "owner_name", "owner", "owner_username", "is_tenant_occupied",
            "monthly_maintenance", "is_active", "created_at",
        ]


class FlatCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flat
        fields = [
            "wing", "flat_no", "floor", "area_sqft", "owner_name",
            "owner", "is_tenant_occupied", "monthly_maintenance", "is_active",
        ]


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
