from django.conf import settings
from django.db import models


class Expense(models.Model):
    """Society expense — visible read-only to all residents for transparency."""

    CATEGORY_CHOICES = [
        ("maintenance", "Maintenance"), ("security", "Security"),
        ("housekeeping", "Housekeeping"), ("utilities", "Utilities"),
        ("repairs", "Repairs"), ("events", "Events"), ("salaries", "Salaries"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other", db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_to = models.CharField(max_length=120, blank=True, help_text="Vendor / staff name")
    description = models.TextField(blank=True)
    receipt_image = models.ImageField(upload_to="expenses/receipts/", blank=True, null=True)
    expense_date = models.DateField()
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="expenses_added"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [models.Index(fields=["category", "expense_date"])]

    def __str__(self):
        return f"{self.title} - ₹{self.amount}"
