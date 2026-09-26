from rest_framework import serializers

from API.apps.announcements.models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = Announcement
        fields = [
            "id", "title", "body", "attachment", "pinned",
            "expiry_date", "created_by", "created_by_name",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_by", "is_active", "created_at", "updated_at"]

    def validate_attachment(self, value):
        import os
        from django.conf import settings as dj_settings
        if value:
            ext = os.path.splitext(value.name)[1].lower()
            allowed = [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xlsx"]
            if ext not in allowed:
                raise serializers.ValidationError(f"Unsupported file type {ext}. Allowed: {allowed}")
            if value.size > dj_settings.MAX_UPLOAD_SIZE:
                raise serializers.ValidationError("File exceeds 5MB limit.")
        return value
