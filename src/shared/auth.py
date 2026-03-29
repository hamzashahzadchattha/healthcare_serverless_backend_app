"""JWT verification middleware — require_auth and require_admin decorators."""

import functools
from typing import Any

from src.shared.exceptions import ForbiddenError, UnauthorizedError


def get_sub(claims: dict[str, Any]) -> str:
    """Return the sub claim from a decoded JWT claims dict."""
    return claims.get("sub", "")


def is_admin(claims: dict[str, Any]) -> bool:
    """Return True if the caller belongs to the admin Cognito group."""
    # API Gateway HTTP API v2 payload stringifies list values into e.g. "['admin']"
    groups = str(claims.get("cognito:groups", ""))
    return "admin" in groups


def require_auth(handler: Any) -> Any:
    """Decorator that ensures AWS API Gateway JWT Authorizer verified the token and extracts claims."""

    @functools.wraps(handler)
    def wrapper(event: dict[str, Any], context: Any) -> Any:
        try:
            # Under HTTP API JWT Authorizer, claims are injected here natively by AWS
            claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        except KeyError:
            # This triggers if accessed without API Gateway or missing Authorizer attachment
            raise UnauthorizedError("No API Gateway JWT claims found")
            
        # Map claims to the legacy local path for backwards compatibility with handler logic
        event.setdefault("requestContext", {}).setdefault("authorizer", {})["claims"] = claims
        return handler(event, context)

    return wrapper


def require_admin(handler: Any) -> Any:
    """Decorator that enforces admin group membership after JWT verification."""

    @functools.wraps(handler)
    def _admin_inner(event: dict[str, Any], context: Any) -> Any:
        # Claims are already injected by require_auth at this point
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        if not is_admin(claims):
            raise ForbiddenError("Admin access required")
        return handler(event, context)

    return require_auth(_admin_inner)


def assert_patient_access(claims: dict[str, Any], patient_cognito_sub: str | None) -> None:
    """Raise ForbiddenError unless the caller owns the patient record or is an admin."""
    if is_admin(claims):
        return
    if patient_cognito_sub is None or get_sub(claims) != patient_cognito_sub:
        raise ForbiddenError("Access to this patient record is not permitted")

