from django.conf import settings
from django.db import models


class Announcement(models.Model):
    title = models.CharField(max_length=150)
    body = models.TextField()
    attachment = models.FileField(upload_to="announcements/", blank=True, null=True)
    pinned = models.BooleanField(default=False)
    expiry_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="announcements"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-created_at"]
        indexes = [models.Index(fields=["pinned", "created_at"])]

    def __str__(self):
        return self.title
