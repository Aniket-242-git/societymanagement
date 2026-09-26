"""Role-based permission classes."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


def user_role(user):
    return getattr(user, "role", None)


class IsAdmin(BasePermission):
    """Society admin / super admin only."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or user_role(u) == "admin"))


class IsAdminOrCommittee(BasePermission):
    """Admin + committee members (approve payments, post announcements)."""

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated
            and (u.is_superuser or user_role(u) in ("admin", "committee"))
        )


class IsResident(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and user_role(u) in ("resident", "owner"))


class IsAdminOrReadOnly(BasePermission):
    """Everyone can read; only admin/committee can write."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return u.is_superuser or user_role(u) in ("admin", "committee")
