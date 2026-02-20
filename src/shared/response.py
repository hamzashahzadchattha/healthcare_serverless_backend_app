"""Centralised HTTP response builder — all Lambda handlers must use this module."""

import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


_ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN")

_BASE_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": _ALLOWED_ORIGIN,
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}


class _HealthcareJSONEncoder(json.JSONEncoder):
    """Extends the default encoder to handle types returned by psycopg2."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _serialise(body: dict[str, Any]) -> str:
    return json.dumps(body, cls=_HealthcareJSONEncoder)


def success(
    data: Any,
    status_code: int = 200,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a successful API Gateway HTTP response.

    Args:
        data: The response payload. Must be JSON-serialisable.
        status_code: HTTP status code. Defaults to 200.
        meta: Optional pagination or supplementary metadata.

    Returns:
        API Gateway proxy response dict.
    """
    body: dict[str, Any] = {"success": True, "data": data}
    if meta is not None:
        body["meta"] = meta
    return {
        "statusCode": status_code,
        "headers": _BASE_HEADERS,
        "body": _serialise(body),
    }


def error(
    message: str,
    error_code: str,
    status_code: int = 500,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an error API Gateway HTTP response.

    Args:
        message: Human-readable error description. Must not contain PHI.
        error_code: Machine-readable slug e.g. 'VALIDATION_ERROR'.
        status_code: HTTP status code.
        details: Optional structured details for debugging (no PHI allowed here).

    Returns:
        API Gateway proxy response dict.
    """
    body: dict[str, Any] = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
        },
    }
    if details:
        body["error"]["details"] = details
    return {
        "statusCode": status_code,
        "headers": _BASE_HEADERS,
        "body": _serialise(body),
    }


def from_exception(exc: Any) -> dict[str, Any]:
    """Convert a typed HealthcarePlatformError directly into an HTTP response."""
    return error(
        message=exc.message,
        error_code=exc.error_code,
        status_code=exc.http_status,
        details=exc.details if exc.details else None,
    )
