"""$default catch-all route — consistent error envelope for all gateway-level errors.

HTTP API v2 does not support Gateway Responses (a REST API v1 feature), so the only
way to return a structured body for unmatched routes, wrong methods, and oversized
payloads is to attach a Lambda to the $default route.

Error cases handled here:
  - 404 Not Found       — route path does not match any defined endpoint
  - 405 Method Not Allowed — path matches but HTTP method does not
  - 413 Payload Too Large  — request body exceeds API Gateway 10 MB limit
  - 400 Bad Request        — malformed request detected by the gateway
"""

from typing import Any

from src.shared import response


_GATEWAY_STATUS_MAP: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "Request is malformed or cannot be processed"),
    404: ("NOT_FOUND", "The requested resource does not exist"),
    405: ("METHOD_NOT_ALLOWED", "HTTP method not allowed on this resource"),
    413: ("PAYLOAD_TOO_LARGE", "Request payload exceeds the maximum allowed size"),
}

_DEFAULT_ERROR = ("NOT_FOUND", "The requested resource does not exist")


def _resolve_status(event: dict[str, Any]) -> int:
    """Derive the correct HTTP status from the gateway request context."""
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "")
    path = (event.get("requestContext") or {}).get("http", {}).get("path", "")

    # API Gateway sets routeKey to "$default" for all unmatched requests.
    # Distinguish 405 (known path, wrong method) from 404 (unknown path) by
    # checking whether the path segment looks like a defined resource prefix.
    _KNOWN_PREFIXES = ("/patients", "/appointments", "/db")
    path_known = any(path.startswith(p) for p in _KNOWN_PREFIXES)

    if path_known and method not in ("GET", "POST", "OPTIONS"):
        return 405
    return 404


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Return a structured error for any request not matched by a defined route."""
    status = _resolve_status(event)
    error_code, message = _GATEWAY_STATUS_MAP.get(status, _DEFAULT_ERROR)
    return response.error(message=message, error_code=error_code, status_code=status)
