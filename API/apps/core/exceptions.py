"""Custom DRF exception handler that forces the standard envelope on errors.

Also builds a *human readable* top-level message from serializer errors so
the UI never shows a generic "Validation failed" when the API knows exactly
what went wrong (e.g. "A user with that username already exists.").
"""
from rest_framework.views import exception_handler

from API.apps.core.responses import api_response


def _flatten_errors(detail, prefix=""):
    """Turn nested DRF error payloads into {field: [messages]} + first message."""
    errors = {}

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}{k}" if not path else f"{path}.{k}")
        elif isinstance(node, list):
            msgs = []
            for item in node:
                if isinstance(item, (dict, list)):
                    walk(item, path)
                else:
                    msgs.append(str(item))
            if msgs:
                errors.setdefault(path or "detail", []).extend(msgs)
        else:
            errors.setdefault(path or "detail", []).append(str(node))

    walk(detail, prefix)
    return errors


def _first_message(errors):
    """Pick the most specific message; prefer non-non_field errors."""
    if not errors:
        return "Request failed"
    for key in ("non_field_errors", "detail"):
        if key in errors and errors[key]:
            return errors[key][0]
    for msgs in errors.values():
        if msgs:
            return msgs[0]
    return "Validation failed"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> let Django produce a 500 (logged normally)
        return None

    detail = response.data
    status_code = response.status_code

    if isinstance(detail, dict):
        errors = {k: (v if isinstance(v, list) else [str(v)]) for k, v in detail.items()}
        flat = _flatten_errors(detail)
        if "detail" in flat and len(flat) == 1:
            message = flat["detail"][0]
            errors = None
        else:
            message = _first_message(flat)
            if message == "Validation failed" and status_code != 400:
                message = f"Request failed ({status_code})"
            errors = flat
    elif isinstance(detail, list):
        flat = _flatten_errors({"detail": detail})
        message = _first_message(flat)
        errors = flat if status_code == 400 else None
        if status_code == 401 and not message.startswith("Given"):
            message = flat.get("detail", ["Authentication failed"])[0]
    else:
        errors = None
        message = str(detail)

    return api_response(
        success=False,
        message=message,
        errors=errors,
        status=status_code,
    )


def first_error_message(errors):
    """Public helper: human readable message from a serializer .errors dict."""
    flat = _flatten_errors(dict(errors)) if isinstance(errors, dict) else _flatten_errors(errors)
    msg = _first_message(flat)
    return msg if msg != "Validation failed" else "Please correct the highlighted fields."
