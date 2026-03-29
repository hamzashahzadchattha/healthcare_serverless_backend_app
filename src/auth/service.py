"""Shared Cognito client, request parsing, and error conversion for auth handlers."""

import json
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.shared.exceptions import (
    DuplicateRecordError,
    ExternalServiceError,
    RateLimitExceededError,
    UnauthorizedError,
    ValidationError,
)
from src.shared.observability import logger

# Module-level client — reused across warm invocations
cognito_client = boto3.client("cognito-idp", region_name=os.environ.get("REGION", "us-east-1"))
CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID", "")


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """Parse and return the JSON request body, raising ValidationError on failure."""
    raw = event.get("body")
    if not raw:
        raise ValidationError("Request body is required")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be valid JSON") from exc


def require_fields(body: dict[str, Any], *fields: str) -> None:
    """Raise ValidationError if any required field is missing or blank."""
    missing = [f for f in fields if not body.get(f)]
    if missing:
        raise ValidationError("Missing required fields", details={"missing": missing})


# Cognito error code → typed application exception mappings per operation.
# Unrecognised codes are converted to ExternalServiceError so callers always
# receive a structured response instead of a raw 500.

_SIGNUP_ERRORS: dict[str, Any] = {
    "UsernameExistsException": lambda _: DuplicateRecordError("An account with this email already exists"),
    "InvalidPasswordException": lambda _: ValidationError("Password does not meet requirements"),
    "InvalidParameterException": lambda e: ValidationError(e.response["Error"]["Message"]),
    "TooManyRequestsException": lambda _: RateLimitExceededError("Too many requests — please try again later"),
    "LimitExceededException": lambda _: RateLimitExceededError("Signup limit exceeded — please try again later"),
}

_VERIFY_ERRORS: dict[str, Any] = {
    "CodeMismatchException": lambda _: ValidationError("Invalid or expired verification code"),
    "ExpiredCodeException": lambda _: ValidationError("Invalid or expired verification code"),
    "UserNotFoundException": lambda _: ValidationError("No account found for this email"),
    "NotAuthorizedException": lambda _: ValidationError("Account is already confirmed"),
    "TooManyRequestsException": lambda _: RateLimitExceededError("Too many requests — please try again later"),
    "LimitExceededException": lambda _: RateLimitExceededError("Too many attempts — please try again later"),
    "TooManyFailedAttemptsException": lambda _: RateLimitExceededError("Too many failed attempts — please try again later"),
}

_SIGNIN_ERRORS: dict[str, Any] = {
    "NotAuthorizedException": lambda _: UnauthorizedError("Invalid email or password"),
    "UserNotFoundException": lambda _: UnauthorizedError("Invalid email or password"),
    "UserNotConfirmedException": lambda _: ValidationError("Email not verified. Check your inbox for the verification code."),
    "PasswordResetRequiredException": lambda _: ValidationError("Password reset required"),
    "InvalidParameterException": lambda e: ValidationError(e.response["Error"]["Message"]),
    "TooManyRequestsException": lambda _: RateLimitExceededError("Too many requests — please try again later"),
}

_LOGOUT_ERRORS: dict[str, Any] = {
    "NotAuthorizedException": lambda _: UnauthorizedError("Invalid or expired access token"),
    "TooManyRequestsException": lambda _: RateLimitExceededError("Too many requests — please try again later"),
}


def cognito_error_to_app_exception(exc: ClientError, mapping: dict[str, Any]) -> "HealthcarePlatformError":
    """Convert a Cognito ClientError to a typed application exception and return it.

    Returns (does not raise) so the caller can raise it inside the try block,
    ensuring the handler's except HealthcarePlatformError clause catches it.
    Raising from inside an except clause propagates past subsequent except
    clauses in the same try block — returning avoids that Python scoping issue.
    """
    from src.shared.exceptions import HealthcarePlatformError  # noqa: F401 — type hint only

    code = exc.response["Error"]["Code"]
    factory = mapping.get(code)
    if factory:
        return factory(exc)
    logger.warning("Unhandled Cognito error", extra={"cognito_error_code": code})
    return ExternalServiceError("Authentication service error")
