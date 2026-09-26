from django.urls import path

from API.apps.reports.views import (
    CollectionReportView, DashboardStatsView, ExcelExportView, IncomeExpenseView,
)

urlpatterns = [
    path("reports/dashboard/", DashboardStatsView.as_view(), name="report-dashboard"),
    path("reports/collections/", CollectionReportView.as_view(), name="report-collections"),
    path("reports/income-expense/", IncomeExpenseView.as_view(), name="report-income-expense"),
    path("reports/export/<str:kind>/", ExcelExportView.as_view(), name="report-export"),
]
