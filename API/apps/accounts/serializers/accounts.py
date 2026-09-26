from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from API.apps.accounts.models import User


class LoginSerializer(serializers.Serializer):
    """Accepts either a username OR a registered mobile number."""

    username = serializers.CharField(help_text="Username or registered mobile number")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs["username"].strip()
        # allow login with mobile number (normalize common formats)
        digits = "".join(ch for ch in identifier if ch.isdigit())
        user = None
        if len(digits) >= 10 and identifier == digits:
            candidates = [digits[-10:], f"+91{digits[-10:]}", f"0{digits[-10:]}"]
            match = (
                User.objects.filter(phone__in=candidates)
                .order_by("username")  # deterministic when duplicates exist
                .first()
            )
            if match:
                user = authenticate(username=match.username, password=attrs["password"])
        if user is None:
            user = authenticate(username=identifier, password=attrs["password"])
        if user is None:
            raise serializers.ValidationError({"detail": "Invalid username/mobile number or password."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account is deactivated. Contact the society admin."})
        attrs["user"] = user
        return attrs

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}


class UserSerializer(serializers.ModelSerializer):
    flat_id = serializers.SerializerMethodField()
    flat_label = serializers.SerializerMethodField()
    flats = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email", "phone",
            "role", "is_active", "must_reset_password", "date_joined",
            "flat_id", "flat_label", "flats",
        ]
        read_only_fields = ["date_joined"]

    def _flats(self, obj):
        prefetched = getattr(obj, "prefetch_flats", None)
        if prefetched is not None:
            return list(prefetched)
        return list(obj.owned_flats.select_related("wing").all())

    def get_flat_id(self, obj):
        fl = self._flats(obj)
        return fl[0].id if fl else None

    def get_flat_label(self, obj):
        fl = self._flats(obj)
        return str(fl[0]) if fl else ""

    def get_flats(self, obj):
        return [{"id": f.id, "label": str(f)} for f in self._flats(obj)]


def _dup_message(field_label, value):
    return f"{field_label} '{value}' is already registered to another user."


class UserCreateSerializer(serializers.ModelSerializer):
    """Admin creates login credentials for a flat owner / resident.

    Optionally pass `flat` (id) to map the new user to a flat in one step —
    the flat's owner FK is set and its owner_name synced automatically.
    A user may be mapped to MULTIPLE flats over time (one flat per user record).
    """

    password = serializers.CharField(write_only=True, min_length=8)
    flat = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "role", "password", "flat"]

    def validate_username(self, value):
        qs = User.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(_dup_message("Username", value))
        return value

    def validate_phone(self, value):
        value = (value or "").strip()
        if value:
            qs = User.objects.filter(phone=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(_dup_message("Mobile number", value))
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if value:
            qs = User.objects.filter(email__iexact=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(_dup_message("Email", value))
        return value

    def validate_flat(self, value):
        from API.apps.flats.models import Flat
        if value:
            flat = Flat.objects.filter(pk=value, is_active=True).first()
            if flat is None:
                raise serializers.ValidationError("Active flat not found.")
            if flat.owner_id and (not self.instance or flat.owner_id != self.instance.pk):
                raise serializers.ValidationError(
                    f"Flat {flat} is already mapped to user '{flat.owner.username}'. "
                    "Unmap it first or choose another flat."
                )
            self._flat = flat
        else:
            self._flat = None
        return value

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("flat", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.must_reset_password = True  # force reset on first login
        user.save()
        flat = getattr(self, "_flat", None)
        if flat is not None:
            flat.owner = user
            if not flat.owner_name or flat.owner_name.startswith("Owner"):
                full = user.get_full_name()
                if full:
                    flat.owner_name = full
            flat.save()
        return user


class UserUpdateWithFlatSerializer(serializers.ModelSerializer):
    """Admin edits a user and can (re)map their flats in one call.

    `flat` = single flat id (replaces all mappings), or
    `flats` = list of flat ids — a user CAN own MULTIPLE flats.
    """

    flat = serializers.IntegerField(required=False, allow_null=True)
    flats = serializers.ListField(child=serializers.IntegerField(), required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role", "is_active", "flat", "flats"]

    def validate_phone(self, value):
        value = (value or "").strip()
        if value:
            qs = User.objects.filter(phone=value).exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(_dup_message("Mobile number", value))
        return value

    def validate_email(self, value):
        value = (value or "").strip()
        if value:
            qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(_dup_message("Email", value))
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        from API.apps.flats.models import Flat
        flat_id = validated_data.pop("flat", "__unset__")
        flat_ids = validated_data.pop("flats", "__unset__")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if flat_ids != "__unset__" or flat_id != "__unset__":
            target_ids = []
            if flat_ids != "__unset__" and flat_ids:
                target_ids = [int(x) for x in flat_ids]
            elif flat_id not in ("__unset__", None):
                target_ids = [int(flat_id)]
            wanted = set(target_ids)
            if wanted:
                flats = list(Flat.objects.filter(pk__in=wanted, is_active=True))
                found = {f.id for f in flats}
                missing = wanted - found
                if missing:
                    raise serializers.ValidationError(
                        {"flats": f"Some flats not found or inactive: {sorted(missing)}"}
                    )
                taken = [f for f in flats if f.owner_id and f.owner_id != instance.pk]
                if taken:
                    labels = ", ".join(f"{f} -> {f.owner.username}" for f in taken)
                    raise serializers.ValidationError({"flats": f"Already mapped: {labels}"})
            # unmap flats no longer assigned
            Flat.objects.filter(owner=instance).exclude(pk__in=wanted).update(owner=None)
            full = instance.get_full_name()
            for f in flats if wanted else []:
                changed = False
                if f.owner_id != instance.pk:
                    f.owner = instance
                    changed = True
                if full and (not f.owner_name or f.owner_name.startswith("Owner")):
                    f.owner_name = full
                    changed = True
                if changed:
                    f.save()
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
