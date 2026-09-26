"""Shared helpers for list endpoints: search + backend pagination."""
from django.conf import settings
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination


def build_search_q(term, fields):
    """OR-combined icontains Q over dotted field paths. None if no term."""
    if not term:
        return None
    q = Q()
    for f in fields:
        q |= Q(**{f"{f}__icontains": term})
    return q


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
