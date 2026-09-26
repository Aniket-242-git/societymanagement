import os

from django.conf import settings as dj_settings
from rest_framework import serializers

from API.apps.expenses.models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    added_by_name = serializers.CharField(source="added_by.username", read_only=True, default=None)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id", "title", "category", "category_display", "amount", "paid_to",
            "description", "receipt_image", "expense_date",
            "added_by", "added_by_name", "created_at",
        ]
        read_only_fields = ["added_by", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_receipt_image(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in dj_settings.ALLOWED_IMAGE_EXTENSIONS:
            raise serializers.ValidationError(f"Unsupported image type {ext}.")
        if value.size > dj_settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError("Receipt image exceeds 5MB limit.")
        return value
