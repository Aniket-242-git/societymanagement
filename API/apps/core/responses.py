"""Shared API response envelope.

Every endpoint returns:
{
  "success": true|false,
  "message": "...",
  "data": {...} | [...] | null,
  "errors": {...} | null
}
"""
from rest_framework.response import Response


def api_response(success, message, data=None, errors=None, status=200):
    return Response(
        {
            "success": success,
            "message": message,
            "data": data,
            "errors": errors,
        },
        status=status,
    )


def api_success(message="OK", data=None, status=200):
    return api_response(True, message, data=data, status=status)


def api_error(message="Error", errors=None, status=400):
    return api_response(False, message, data=None, errors=errors, status=status)
