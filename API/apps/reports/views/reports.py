from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from API.apps.core.permissions import IsAdminOrCommittee
from API.apps.core.responses import api_success
from API.apps.reports import services as rpt


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_success(data=rpt.dashboard_stats(request.user))


class CollectionReportView(APIView):
    permission_classes = [IsAdminOrCommittee]

    def get(self, request):
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        return api_success(data={
            "summary": rpt.collection_summary(year, month),
            "due_list": rpt.flat_wise_due_list(int(year), int(month)) if year and month else [],
        })


class IncomeExpenseView(APIView):
    permission_classes = [IsAdminOrCommittee]

    def get(self, request):
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        return api_success(data=rpt.income_vs_expense(year, month))


class ExcelExportView(APIView):
    """GET /api/v1/reports/export/<kind>/?year=&month= -> xlsx download."""

    permission_classes = [IsAdminOrCommittee]

    def get(self, request, kind):
        from django.http import FileResponse
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        y = int(year) if year else None
        m = int(month) if month else None
        if kind == "collections":
            bio = rpt.export_collections_xlsx(y, m)
            fname = f"collections_{year or 'all'}.xlsx"
        elif kind == "expenses":
            bio = rpt.export_expenses_xlsx(y, m)
            fname = f"expenses_{year or 'all'}.xlsx"
        elif kind == "dues":
            if not (y and m):
                return api_error_via_success_only()
            bio = rpt.export_due_list_xlsx(y, m)
            fname = f"due_list_{y}-{m:02d}.xlsx"
        else:
            return api_error_via_success_only()
        return FileResponse(
            bio, as_attachment=True, filename=fname,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def api_error_via_success_only():
    from API.apps.core.responses import api_error
    return api_error("Invalid export parameters.", status=400)
