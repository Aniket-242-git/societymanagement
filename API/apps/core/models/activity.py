from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """Centralized global audit trail across modules.

    Written via log_activity() helper (service layer) rather than scattered
    inline code, so every create/update/delete can be traced.
    """

    ACTION_CHOICES = [
        ("create", "Create"), ("update", "Update"), ("delete", "Delete"),
        ("login", "Login"), ("approve", "Approve"), ("reject", "Reject"),
        ("view", "View"), ("other", "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="activity_logs",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=60)
    object_id = models.CharField(max_length=30, blank=True)
    remark = models.CharField(max_length=250, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["user", "timestamp"])]

    def __str__(self):
        return f"{self.user} {self.action} {self.model_name}#{self.object_id}"
