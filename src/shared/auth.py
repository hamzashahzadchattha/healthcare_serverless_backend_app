"""JWT verification middleware — require_auth and require_admin decorators."""

import functools
import json
import os
from typing import Any

import urllib.error
import urllib.request

import jwt
from jwt.algorithms import RSAAlgorithm

from src.shared.exceptions import ForbiddenError, UnauthorizedError

_jwks_cache: dict[str, Any] = {}

_JWKS_URL = (
    f"https://cognito-idp.{os.environ['REGION']}.amazonaws.com"
    f"/{os.environ['COGNITO_USER_POOL_ID']}/.well-known/jwks.json"
)


def get_sub(claims: dict[str, Any]) -> str:
    """Return the sub claim from a decoded JWT claims dict."""
    return claims["sub"]


def is_admin(claims: dict[str, Any]) -> bool:
    """Return True if the caller belongs to the admin Cognito group."""
    groups = claims.get("cognito:groups") or []
    return "admin" in groups


def _refresh_jwks_cache() -> None:
    """Fetch the JWKS endpoint and repopulate the module-level cache."""
    global _jwks_cache
    try:
        req = urllib.request.Request(_JWKS_URL)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            keys = data.get("keys", [])
            _jwks_cache = {key["kid"]: key for key in keys}
    except urllib.error.URLError as exc:
        # We raise a generic Exception so the outer standard exception handler captures it
        raise Exception("Failed to fetch Cognito JWKS keys") from exc


def require_auth(handler: Any) -> Any:
    """Decorator that verifies a Cognito RS256 JWT before calling the handler."""

    @functools.wraps(handler)
    def wrapper(event: dict[str, Any], context: Any) -> Any:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        auth_header = headers.get("authorization", "")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise UnauthorizedError("Authorization header missing or malformed")

        token = auth_header[len("Bearer "):]

        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError:
            raise UnauthorizedError("Authorization header missing or malformed")

        kid = unverified_header.get("kid")
        if kid not in _jwks_cache:
            _refresh_jwks_cache()

        if kid not in _jwks_cache:
            raise UnauthorizedError("Authorization header missing or malformed")

        public_key = RSAAlgorithm.from_jwk(json.dumps(_jwks_cache[kid]))

        try:
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token has expired")
        except jwt.InvalidSignatureError:
            raise UnauthorizedError("Token signature is invalid")

        event.setdefault("requestContext", {}).setdefault("authorizer", {})["claims"] = claims
        return handler(event, context)

    return wrapper


def require_admin(handler: Any) -> Any:
    """Decorator that enforces admin group membership after JWT verification."""

    @functools.wraps(handler)
    def _admin_inner(event: dict[str, Any], context: Any) -> Any:
        # Claims are already injected by require_auth at this point
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        groups = claims.get("cognito:groups") or []
        if "admin" not in groups:
            raise ForbiddenError("Admin access required")
        return handler(event, context)

    return require_auth(_admin_inner)


def assert_patient_access(claims: dict[str, Any], patient_cognito_sub: str | None) -> None:
    """Raise ForbiddenError unless the caller owns the patient record or is an admin."""
    if is_admin(claims):
        return
    if patient_cognito_sub is None or get_sub(claims) != patient_cognito_sub:
        raise ForbiddenError("Access to this patient record is not permitted")
