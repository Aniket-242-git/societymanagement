"""Expense management API.

Residents see expenses (read-only, transparency); admin/committee can CRUD.
List supports ?search= (title / vendor / description) and backend pagination
(page size from .env PAGE_SIZE).
"""
from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from API.apps.core.exceptions import first_error_message
from API.apps.core.pagination import StandardPagination
from API.apps.core.permissions import IsAdminOrReadOnly
from API.apps.core.responses import api_error, api_success
from API.apps.expenses.models import Expense
from API.apps.expenses.serializers import ExpenseSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    """Expense CRUD — visible to all residents for transparency."""

    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = StandardPagination
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        qs = (
            Expense.objects.filter(is_active=True)
            .select_related("added_by")
            .order_by("-expense_date", "-created_at")
        )
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(paid_to__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
            )
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        # month-wise filter: ?year=2026&month=9 on expense_date
        from API.apps.core.pagination import parse_month_filter
        y, m = parse_month_filter(self.request)
        if y:
            qs = qs.filter(expense_date__year=y)
        if m:
            qs = qs.filter(expense_date__month=m)
        return qs

    # ------------------------------------------------------------- list
    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        if page is not None:
            return self.get_paginated_response(ExpenseSerializer(page, many=True).data)
        return api_success(data=ExpenseSerializer(self.get_queryset(), many=True).data)

    def retrieve(self, request, pk=None, *args, **kwargs):
        try:
            obj = self.get_queryset().get(pk=pk)
        except Expense.DoesNotExist:
            return api_error("Expense not found", status=404)
        return api_success(data=ExpenseSerializer(obj).data)

    # ------------------------------------------------------------- create
    def create(self, request, *args, **kwargs):
        ser = ExpenseSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        with transaction.atomic():
            ser.save(added_by=request.user)
        return api_success(
            "Expense added successfully",
            data=ExpenseSerializer(ser.instance).data,
            status=201,
        )

    # ------------------------------------------------------------- update
    def partial_update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Expense.objects.get(pk=pk, is_active=True)
        except Expense.DoesNotExist:
            return api_error("Expense not found", status=404)
        ser = ExpenseSerializer(obj, data=request.data, partial=True,
                                context={"request": request})
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Expense updated successfully", data=ser.data)

    update = partial_update

    # ------------------------------------------------------------- soft delete
    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            obj = Expense.objects.get(pk=pk, is_active=True)
        except Expense.DoesNotExist:
            return api_error("Expense not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return api_success("Expense deleted successfully")
