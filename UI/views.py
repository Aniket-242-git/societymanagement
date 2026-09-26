"""Server-rendered UI pages (Django views). All data operations go through
the DRF API via the central jQuery ajaxRequest() wrapper."""
from django.conf import settings as dj_settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from API.apps.accounts.models import User


def _ctx(request, extra=None):
    """Common template context (page size for JS pagination comes from .env)."""
    c = {"page_size": dj_settings.PAGE_SIZE}
    if extra:
        c.update(extra)
    return c


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html", _ctx(request))


def ui_login(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)  # PhoneOrUsernameBackend: username OR mobile
        if user is not None and user.is_active:
            login(request, user)
            return redirect("dashboard")
        error = "Invalid username or password."
    return render(request, "login.html", _ctx(request,  {"error": error}))


def ui_logout(request):
    logout(request)
    return redirect("landing")


@login_required
def dashboard(request):
    user = request.user
    is_staff = user.is_staff_role
    first_flat = user.owned_flats.order_by("wing__name", "flat_no").first()
    context = {
        "is_admin": is_staff,
        "is_resident": not is_staff,
        "flat": first_flat,
        "flats": [] if is_staff else list(user.owned_flats.select_related("wing")),
    }
    template = "admin/dashboard.html" if is_staff else "resident/dashboard.html"
    context["page_size"] = dj_settings.PAGE_SIZE
    return render(request, template, context)


# ---- admin pages -----------------------------------------------------------
def _staff_required(view_func):
    from functools import wraps

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff_role:
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


@_staff_required
def flats_page(request):
    return render(request, "admin/flats.html", _ctx(request))


@_staff_required
def services_page(request):
    return render(request, "admin/services.html", _ctx(request))


@_staff_required
def users_page(request):
    return render(request, "admin/users.html", _ctx(request))


@_staff_required
def announcements_page(request):
    return render(request, "admin/announcements.html", _ctx(request))


@_staff_required
def payments_page(request):
    return render(request, "admin/payments.html", _ctx(request))


@_staff_required
def expenses_page(request):
    return render(request, "admin/expenses.html", _ctx(request))


@_staff_required
def issues_page(request):
    return render(request, "admin/issues.html", _ctx(request))


@_staff_required
@_staff_required
def settings_page(request):
    return render(request, "admin/settings.html", _ctx(request))


def reports_page(request):
    return render(request, "admin/reports.html", _ctx(request))


# ---- resident pages --------------------------------------------------------
def _resident_page(template):
    def deco(view_func):
        from functools import wraps

        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.is_staff_role:
                return redirect("dashboard")
            return render(request, template)
        return _wrapped
    return deco


@_resident_page("resident/payments.html")
def resident_payments(request):
    pass


@_resident_page("resident/issues.html")
def resident_issues(request):
    pass


@_resident_page("resident/announcements.html")
def resident_announcements(request):
    pass


@_resident_page("resident/expenses.html")
def resident_expenses(request):
    pass
