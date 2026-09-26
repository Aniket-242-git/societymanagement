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
            detail = ser.errors.get("detail") or ser.errors
            return api_error(
                "Invalid username or password." if "detail" in ser.errors else "Validation failed",
                errors=ser.errors if "detail" not in ser.errors else None,
                status=status.HTTP_401_UNAUTHORIZED if "detail" in ser.errors else 400,
            )
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
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("Profile updated successfully", data=ser.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PasswordChangeSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
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
        qs = self.queryset
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return api_success(data=self.get_serializer(qs, many=True).data)

    def create(self, request, *args, **kwargs):
        ser = UserCreateSerializer(data=request.data)
        if not ser.is_valid():
            return api_error("Validation failed", errors=ser.errors)
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
            return api_error("Validation failed", errors=ser.errors)
        ser.save()
        return api_success("User updated successfully", data=UserSerializer(user).data)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return api_error("User not found", status=404)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return api_success("User deactivated successfully")

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
