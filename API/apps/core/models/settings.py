from django.conf import settings
from django.db import models


class ExpenseCategory(models.Model):
    """Master list of expense categories, managed from the Settings tab.

    Expenses store the category as a plain string (legacy choices remain valid);
    this table drives the dropdowns in the UI so admins can add/rename/disable
    categories without a code change.
    """

    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Expense categories"

    def __str__(self):
        return self.name


class AppSetting(models.Model):
    """Simple key/value store for global settings (e.g. society name)."""

    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=250, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
