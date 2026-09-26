from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with society role and flat mapping.

    roles:
      admin     - society admin / super privileges
      committee - limited admin (approve payments, post announcements)
      resident  - flat owner / resident
    """

    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("committee", "Committee Member"),
        ("resident", "Resident"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="resident", db_index=True)
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.ImageField(upload_to="profiles/", blank=True, null=True)
    must_reset_password = models.BooleanField(
        default=False,
        help_text="Force password reset on first login (set when admin creates credentials).",
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == "admin"

    @property
    def is_staff_role(self):
        return self.is_superuser or self.role in ("admin", "committee")
