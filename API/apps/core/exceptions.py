"""Custom DRF exception handler that forces the standard envelope on errors."""
from rest_framework.views import exception_handler

from API.apps.core.responses import api_response


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> let Django produce a 500 (logged normally)
        return None

    detail = response.data
    # Convert DRF error payloads into the shared `errors` dict shape
    if isinstance(detail, dict):
        errors = {k: (v if isinstance(v, list) else [str(v)]) for k, v in detail.items()}
        message = errors.get("detail", ["Request failed"])[0] if "detail" in errors else "Request failed"
        if "detail" in errors and len(errors) == 1:
            errors = None
    elif isinstance(detail, list):
        errors = {"detail": [str(d) for d in detail]}
        message = str(detail[0]) if detail else "Request failed"
    else:
        errors = None
        message = str(detail)

    return api_response(
        success=False,
        message=message,
        errors=errors,
        status=response.status_code,
    )
