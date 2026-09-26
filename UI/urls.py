from django.urls import path

from UI import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("ui/login/", views.ui_login, name="ui-login"),
    path("ui/logout/", views.ui_logout, name="ui-logout"),
    path("ui/dashboard/", views.dashboard, name="dashboard"),
    # admin
    path("ui/admin/flats/", views.flats_page, name="admin-flats"),
    path("ui/admin/services/", views.services_page, name="admin-services"),
    path("ui/admin/users/", views.users_page, name="admin-users"),
    path("ui/admin/announcements/", views.announcements_page, name="admin-announcements"),
    path("ui/admin/payments/", views.payments_page, name="admin-payments"),
    path("ui/admin/expenses/", views.expenses_page, name="admin-expenses"),
    path("ui/admin/issues/", views.issues_page, name="admin-issues"),
    path("ui/admin/reports/", views.reports_page, name="admin-reports"),
    # resident
    path("ui/resident/payments/", views.resident_payments, name="resident-payments"),
    path("ui/resident/issues/", views.resident_issues, name="resident-issues"),
    path("ui/resident/announcements/", views.resident_announcements, name="resident-announcements"),
    path("ui/resident/expenses/", views.resident_expenses, name="resident-expenses"),
]
