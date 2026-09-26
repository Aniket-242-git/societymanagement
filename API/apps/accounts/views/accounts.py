from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from API.apps.accounts.models import User
from API.apps.accounts.serializers import (
    LoginSerializer, PasswordChangeSerializer, UserCreateSerializer,
    UserSerializer, UserUpdateWithFlatSerializer,
)
from API.apps.core.models import ActivityLog
from API.apps.core.exceptions import first_error_message
from API.apps.core.permissions import IsAdmin
from API.apps.core.responses import api_error, api_success


# ------------------------------------------------------------------ JWT login
class LoginView(APIView):
    """POST /api/v1/auth/login/ -> { access, refresh, user }"""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        if not ser.is_valid():
            if "detail" in ser.errors:
                return api_error(ser.errors["detail"][0], status=status.HTTP_401_UNAUTHORIZED)
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        user = ser.validated_data["user"]
        tokens = ser.get_tokens(user)
        ActivityLog.objects.create(user=user, action="login", model_name="User",
                                   object_id=user.id, remark="API login")
        return api_success("Login successful", data={
            **tokens,
            "user": UserSerializer(user).data,
        })


class LogoutView(APIView):
    """Client discards tokens; endpoint kept for symmetry + activity logging."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return api_success("Logged out successfully")


class EnvelopeTokenRefreshView(APIView):
    """POST /api/v1/auth/token/refresh/ wrapped in the standard envelope so
    the jQuery layer can transparently renew an expired access token."""

    permission_classes = [AllowAny]
    authentication_classes = []  # old access token is expired by definition

    def post(self, request):
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.serializers import TokenRefreshSerializer
        ser = TokenRefreshSerializer(data={"refresh": request.data.get("refresh", "")})
        try:
            ser.is_valid(raise_exception=True)
        except (ValidationError, TokenError):
            return api_error("Session expired. Please login again.", status=401)
        return api_success("Token refreshed", data=ser.validated_data)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=UserSerializer(request.user).data)

    def patch(self, request):
        ser = UserSerializer(request.user, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Profile updated successfully", data=ser.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PasswordChangeSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        request.user.set_password(ser.validated_data["new_password"])
        request.user.must_reset_password = False
        request.user.save(update_fields=["password", "must_reset_password"])
        return api_success("Password changed successfully")


# ------------------------------------------------------------------ user mgmt
class UserViewSet(viewsets.ModelViewSet):
    """Admin-only user CRUD. Residents cannot list users."""

    permission_classes = [IsAdmin]
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateWithFlatSerializer
        return UserSerializer

    def list(self, request, *args, **kwargs):
        qs = self.queryset.prefetch_related("owned_flats__wing", "flat_links__flat__wing")
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        active = request.query_params.get("is_active")
        if active in ("true", "false"):
            qs = qs.filter(is_active=active == "true")
        search = request.query_params.get("search")
        if search:
            from API.apps.core.pagination import build_search_q
            q = build_search_q(search, [
                "username", "first_name", "last_name", "email", "phone",
                "owned_flats__flat_no", "owned_flats__owner_name",
            ])
            qs = qs.filter(q).distinct()
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return api_success(data=self.get_serializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        ser = UserCreateSerializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        user = ser.save()
        ActivityLog.objects.create(user=request.user, action="create", model_name="User",
                                   object_id=user.id, remark=f"Created user {user.username}")
        return api_success("User created successfully", data=UserSerializer(user).data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return api_error("User not found", status=404)
        ser = UserUpdateWithFlatSerializer(user, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("User updated successfully", data=UserSerializer(user).data)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return api_error("User not found", status=404)
        if user.is_superuser:
            return api_error("Super admin account cannot be deactivated.")
        # Rule: a resident assigned to flat(s) must have flats revoked first.
        if not user.is_staff_role:
            from API.apps.flats.models import FlatOwner

            flats = list(
                FlatOwner.objects.filter(user=user).select_related("flat", "flat__wing")[:5]
            ) or list(user.owned_flats.select_related("wing")[:5])
            if flats:
                labels = ", ".join(str(f.flat if isinstance(f, FlatOwner) else f) for f in flats)
                return api_error(
                    f"User '{user.username}' is assigned to flat(s): {labels}. "
                    "Revoke the flat(s) first (Edit user → Flats → remove), then deactivate."
                )
        user.is_active = False
        user.save(update_fields=["is_active"])
        ActivityLog.objects.create(user=request.user, action="deactivate", model_name="User",
                                   object_id=user.id, remark=f"Deactivated user {user.username}")
        return api_success("User deactivated successfully")

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def activate(self, request, pk=None):
        """Re-activate a previously deactivated user."""
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return api_error("User not found", status=404)
        if user.is_active:
            return api_error("User is already active.")
        user.is_active = True
        user.save(update_fields=["is_active"])
        ActivityLog.objects.create(user=request.user, action="activate", model_name="User",
                                   object_id=user.id, remark=f"Activated user {user.username}")
        return api_success("User activated successfully", data=UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        """Admin resets a user's password -> forces change on next login."""
        import secrets, string
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return api_error("User not found", status=404)
        alphabet = string.ascii_letters + string.digits
        new_password = "".join(secrets.choice(alphabet) for _ in range(10))
        user.set_password(new_password)
        user.must_reset_password = True
        user.save(update_fields=["password", "must_reset_password"])
        return api_success("Password reset successfully", data={"temporary_password": new_password})
