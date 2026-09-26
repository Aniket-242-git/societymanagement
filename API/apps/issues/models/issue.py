from django.conf import settings
from django.db import models

from API.apps.flats.models import Flat


class Issue(models.Model):
    STATUS_CHOICES = [("open", "Open"), ("in_progress", "In Progress"), ("resolved", "Resolved")]
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")]
    CATEGORY_CHOICES = [
        ("plumbing", "Plumbing"), ("electrical", "Electrical"), ("security", "Security"),
        ("housekeeping", "Housekeeping"), ("elevator", "Elevator"), ("parking", "Parking"),
        ("water", "Water Supply"), ("other", "Other"),
    ]

    flat = models.ForeignKey(Flat, on_delete=models.CASCADE, related_name="issues")
    title = models.CharField(max_length=150)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other", db_index=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open", db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="issues"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["flat", "status"]),
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.title}"

    @property
    def vote_count(self):
        return self.votes.count()


class IssueImage(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="issues/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"image for #{self.issue_id}"


class IssueVote(models.Model):
    """Residents upvote issues to raise visibility."""

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issue_votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("issue", "user")


class IssueComment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issue_comments")
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class IssueResolution(models.Model):
    """Admin resolution record (kept separate from the issue for history)."""

    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name="resolution")
    remark = models.TextField()
    image = models.ImageField(upload_to="issues/resolutions/", blank=True, null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="resolved_issues"
    )
    timestamp = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Issue resolutions"

    def __str__(self):
        return f"resolution for #{self.issue_id}"
