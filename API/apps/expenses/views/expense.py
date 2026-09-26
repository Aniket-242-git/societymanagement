from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from API.apps.core.permissions import IsAdminOrCommittee
from API.apps.core.exceptions import first_error_message
from API.apps.core.responses import api_error, api_success
from API.apps.expenses.models import Expense
from API.apps.expenses.serializers import ExpenseSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    """Read: everyone (transparency). Write: admin/committee only."""

    serializer_class = ExpenseSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminOrCommittee()]

    def get_queryset(self):
        qs = Expense.objects.filter(is_active=True).select_related("added_by")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        month = self.request.query_params.get("month")   # YYYY-MM
        year = self.request.query_params.get("year")
        if year:
            qs = qs.filter(expense_date__year=int(year))
        if month and "-" in month:
            y, m = month.split("-")
            qs = qs.filter(expense_date__year=int(y), expense_date__month=int(m))
        return qs.order_by("-expense_date", "-created_at")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        ser = self.get_serializer
        if page is not None:
            return self.get_paginated_response(ser(page, many=True).data)
        return api_success(data=ser(self.get_queryset(), many=True).data)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save(added_by=request.user)
        return api_success("Expense logged successfully", data=ser.data, status=201)

    def update(self, request, pk=None, *args, **kwargs):
        try:
            obj = Expense.objects.get(pk=pk, is_active=True)
        except Expense.DoesNotExist:
            return api_error("Expense not found", status=404)
        ser = self.get_serializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return api_error(first_error_message(ser.errors), errors=ser.errors)
        ser.save()
        return api_success("Expense updated successfully", data=ser.data)

    def destroy(self, request, pk=None, *args, **kwargs):
        try:
            obj = Expense.objects.get(pk=pk, is_active=True)
        except Expense.DoesNotExist:
            return api_error("Expense not found", status=404)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return api_success("Expense deleted successfully")
