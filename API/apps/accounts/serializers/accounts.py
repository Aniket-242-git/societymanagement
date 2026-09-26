from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from API.apps.accounts.models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None:
            raise serializers.ValidationError({"detail": "Invalid username or password."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account is deactivated."})
        attrs["user"] = user
        return attrs

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}


class UserSerializer(serializers.ModelSerializer):
    flat_id = serializers.IntegerField(source="owned_flats.first.id", read_only=True)
    flat_label = serializers.CharField(source="owned_flats.first.__str__", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email", "phone",
            "role", "is_active", "must_reset_password", "date_joined",
            "flat_id", "flat_label",
        ]
        read_only_fields = ["date_joined"]


class UserCreateSerializer(serializers.ModelSerializer):
    """Admin creates login credentials for a flat owner / resident.

    Optionally pass `flat` (id) to map the new user to a flat in one step —
    the flat's owner FK is set and its owner_name synced automatically.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    flat = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "role", "password", "flat"]

    def validate_flat(self, value):
        from API.apps.flats.models import Flat
        if value:
            flat = Flat.objects.filter(pk=value, is_active=True).first()
            if flat is None:
                raise serializers.ValidationError("Active flat not found.")
            if flat.owner_id and (not self.instance or flat.owner_id != self.instance.pk):
                raise serializers.ValidationError("This flat already has a mapped user.")
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
    """Admin edits a user and can (re)map their flat in one call."""

    flat = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role", "is_active", "flat"]

    @transaction.atomic
    def update(self, instance, validated_data):
        from API.apps.flats.models import Flat
        flat_id = validated_data.pop("flat", "__unset__")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if flat_id != "__unset__":
            Flat.objects.filter(owner=instance).update(owner=None)
            if flat_id:
                flat = Flat.objects.filter(pk=flat_id, is_active=True).first()
                if flat is None:
                    raise serializers.ValidationError({"flat": "Active flat not found."})
                flat.owner = instance
                full = instance.get_full_name()
                if full:
                    flat.owner_name = full
                flat.save()
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
