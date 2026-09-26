import os

from django.conf import settings as dj_settings
from rest_framework import serializers

from API.apps.issues.models import (
    Issue, IssueComment, IssueImage, IssueResolution, IssueVote,
)


def validate_image(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in dj_settings.ALLOWED_IMAGE_EXTENSIONS:
        raise serializers.ValidationError(f"Unsupported image type {ext}.")
    if file.size > dj_settings.MAX_UPLOAD_SIZE:
        raise serializers.ValidationError("Image exceeds 5MB limit.")
    return file


class IssueImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueImage
        fields = ["id", "issue", "image", "uploaded_at"]
        read_only_fields = ["uploaded_at"]


class IssueCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = IssueComment
        fields = ["id", "issue", "user", "user_name", "comment", "created_at"]
        read_only_fields = ["issue", "user", "created_at"]


class IssueResolutionSerializer(serializers.ModelSerializer):
    resolved_by_name = serializers.CharField(source="resolved_by.username", read_only=True, default=None)

    class Meta:
        model = IssueResolution
        fields = ["id", "issue", "remark", "image", "resolved_by", "resolved_by_name", "timestamp"]
        read_only_fields = ["resolved_by", "timestamp"]


# ------------------------------------------------------------------ create
class IssueCreateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(), required=False, write_only=True, allow_empty=True,
    )

    class Meta:
        model = Issue
        fields = ["id", "flat", "title", "description", "category", "priority", "images"]

    def validate_images(self, value):
        for img in value:
            validate_image(img)
        return value

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        request = self.context.get("request")
        validated_data["created_by"] = request.user if request else None
        issue = Issue.objects.create(**validated_data)
        for img in images:
            IssueImage.objects.create(issue=issue, image=img)
        return issue


# ------------------------------------------------------------------ list / detail
class IssueListSerializer(serializers.ModelSerializer):
    flat_label = serializers.CharField(source="flat.__str__", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)
    vote_count = serializers.IntegerField(source="_vote_count", read_only=True)
    comment_count = serializers.IntegerField(source="_comment_count", read_only=True)
    has_voted = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = [
            "id", "flat", "flat_label", "title", "description", "category",
            "status", "priority", "created_by", "created_by_name",
            "vote_count", "comment_count", "has_voted", "created_at",
        ]

    def get_has_voted(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return IssueVote.objects.filter(issue=obj, user=request.user).exists()


class IssueDetailSerializer(IssueListSerializer):
    images = IssueImageSerializer(many=True, read_only=True)
    comments = IssueCommentSerializer(many=True, read_only=True)
    resolution = IssueResolutionSerializer(read_only=True)

    class Meta(IssueListSerializer.Meta):
        fields = IssueListSerializer.Meta.fields + ["images", "comments", "resolution", "updated_at"]


# ------------------------------------------------------------------ approve / status
class IssueStatusSerializer(serializers.Serializer):
    """Separate serializer per action: admin changes status."""

    status = serializers.ChoiceField(choices=["open", "in_progress", "resolved"])


class IssueResolveSerializer(serializers.ModelSerializer):
    """Admin adds resolution remark + optional image; sets status resolved."""

    class Meta:
        model = IssueResolution
        fields = ["remark", "image"]

    def validate_image(self, value):
        if value:
            validate_image(value)
        return value
