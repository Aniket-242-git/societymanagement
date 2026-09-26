"""Shared helpers for list endpoints: search + backend pagination."""
from django.conf import settings
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination


class EnvelopePaginationMixin:
    """Adds paginate_queryset / get_paginated_response to plain DRF ViewSets.

    `rest_framework.viewsets.ViewSet` does NOT include ListModelMixin, so
    self.paginate_queryset() does not exist there — this mixin provides the
    standard paginator API (using the view's `pagination_class`) so both
    ModelViewSet and plain ViewSet list actions can share the same code path.
    """

    def _paginator(self):
        page_size = getattr(self, "page_size", None)
        klass = self.pagination_class or type(
            "_TmpPaginator", (StandardPagination,), {"page_size": page_size}
        )
        return klass()

    def paginate_queryset(self, queryset, request=None, view=None):
        from rest_framework.request import Request

        if request is None:
            request = getattr(self, "request", None)
            if request is not None and not isinstance(request, Request):
                request = None
        if request is None:
            return None
        paginator = self._paginator()
        from rest_framework.exceptions import NotFound

        try:
            page = paginator.paginate_queryset(queryset, request, view=self)
        except NotFound:
            # out-of-range ?page=N -> let DRF return the standard 404 envelope
            raise
        except Exception:
            # any other pagination issue -> fall back to unpaginated list
            return None
        # stash so get_paginated_response can reuse the exact same paginator
        self._instance_paginator = paginator
        return page

    def get_paginated_response(self, data):
        paginator = getattr(self, "_instance_paginator", None) or self._paginator()
        return paginator.get_paginated_response(data)


def build_search_q(term, fields):
    """OR-combined icontains Q over dotted field paths. None if no term."""
    if not term:
        return None
    q = Q()
    for f in fields:
        q |= Q(**{f"{f}__icontains": term})
    return q


def parse_month_filter(request):
    """Read ?year=&month= (or ?month=YYYY-MM) query params.

    Returns (year:int|None, month:int|None). Used by the month-wise filters on
    Payments / Announcements / Expenses list endpoints.
    """
    year = request.query_params.get("year")
    month = request.query_params.get("month")
    y = m = None
    try:
        y = int(year) if year else None
    except (TypeError, ValueError):
        y = None
    if month:
        s = str(month).strip()
        if "-" in s:  # supports month=2026-09 as well
            parts = s.split("-")
            try:
                y = int(parts[0])
                m = int(parts[1])
            except (ValueError, IndexError):
                m = None
        else:
            try:
                m = int(s)
            except ValueError:
                m = None
        if m is not None and not (1 <= m <= 12):
            m = None
    return y, m


class StandardPagination(PageNumberPagination):
    """count / page / total_pages / next / previous / results — newest first.

    `page` size comes from .env (PAGE_SIZE); the frontend simply requests
    `?page=N` and receives at most PAGE_SIZE records per call.
    """

    page_size = settings.PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        from API.apps.core.responses import api_success

        return api_success(
            message="OK",
            data={
                "count": self.page.paginator.count,
                "page": self.page.number,
                "total_pages": self.page.paginator.num_pages,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            },
        )


def paginate_list(view, queryset, serializer_class, message="OK"):
    """Paginate `queryset` with the view's paginator and return the envelope."""
    page = view.paginate_queryset(queryset)
    if page is not None:
        return view.get_paginated_response(serializer_class(page, many=True).data)
    from API.apps.core.responses import api_success

    return api_success(message, data=serializer_class(queryset, many=True).data)
