from django.urls import path

from UI import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("login/", views.ui_login, name="ui-login"),
    path("logout/", views.ui_logout, name="ui-logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # admin
    path("admin/flats/", views.flats_page, name="admin-flats"),
    path("admin/services/", views.services_page, name="admin-services"),
    path("admin/users/", views.users_page, name="admin-users"),
    path("admin/announcements/", views.announcements_page, name="admin-announcements"),
    path("admin/payments/", views.payments_page, name="admin-payments"),
    path("admin/expenses/", views.expenses_page, name="admin-expenses"),
    path("admin/issues/", views.issues_page, name="admin-issues"),
    path("admin/reports/", views.reports_page, name="admin-reports"),
    path("admin/settings/", views.settings_page, name="admin-settings"),
    # resident
    path("resident/payments/", views.resident_payments, name="resident-payments"),
    path("resident/issues/", views.resident_issues, name="resident-issues"),
    path("resident/announcements/", views.resident_announcements, name="resident-announcements"),
    path("resident/expenses/", views.resident_expenses, name="resident-expenses"),
]
