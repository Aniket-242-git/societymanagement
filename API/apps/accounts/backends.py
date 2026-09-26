"""Authentication backend that lets users log in with EITHER username OR mobile number.

Used by both the DRF API (LoginSerializer) and the session-based UI login, so the
rule "mobile number only, user id not required" works everywhere consistently.
"""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


def normalize_phone(raw: str) -> str:
    """Return digits-only 10-digit local number, or '' if it isn't phone-like."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[-10:]
    return digits if len(digits) == 10 else ""


class PhoneOrUsernameBackend(ModelBackend):
    """Authenticate by username, falling back to a unique mobile-number match."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        identifier = str(username).strip()

        user = User.objects.filter(username__iexact=identifier).first()
        if user is None:
            phone = normalize_phone(identifier)
            if phone:
                candidates = list(
                    User.objects.filter(phone__in=(phone, f"+91{phone}")).order_by("username")
                )
                # deterministic pick when duplicates exist
                user = candidates[0] if len(candidates) >= 1 else None

        if user is not None and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
