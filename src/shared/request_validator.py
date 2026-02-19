"""Input validation utilities for Lambda event payloads."""

import json
import re
from typing import Any

from jsonschema import Draft7Validator, FormatChecker

from src.shared.exceptions import ValidationError


_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_body(body_raw: str | None, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate a JSON request body against a JSON Schema.

    Args:
        body_raw: Raw JSON string from the API Gateway event.
        schema: A valid JSON Schema (Draft 7) dict.

    Returns:
        Parsed and validated body dict.

    Raises:
        ValidationError: When the body is missing, not valid JSON, or fails schema.
    """
    if not body_raw:
        raise ValidationError("Request body is required")

    try:
        body: dict[str, Any] = json.loads(body_raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be valid JSON") from exc

    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))

    if errors:
        messages = [
            f"Field '{'.'.join(str(p) for p in err.path) or 'root'}': {err.message}"
            for err in errors
        ]
        raise ValidationError(
            "Request body validation failed",
            details={"field_errors": messages},
        )

    return body


def validate_uuid_path_param(value: str | None, param_name: str) -> str:
    """Validate that a path parameter is a valid UUID v4.

    Args:
        value: Raw string value from the API Gateway event path parameters.
        param_name: Name of the parameter (used only in error messages, not the value).

    Returns:
        Validated UUID string (lowercased).

    Raises:
        ValidationError: When value is missing or not a valid UUID.
    """
    if not value:
        raise ValidationError(f"Path parameter '{param_name}' is required")

    if not _UUID_PATTERN.match(value):
        raise ValidationError(f"Path parameter '{param_name}' must be a valid UUID")

    return value.lower()


def validate_query_param_enum(
    value: str | None,
    param_name: str,
    allowed_values: list[str],
    default: str | None = None,
) -> str | None:
    """Validate that a query string parameter is one of a fixed set of values.

    Args:
        value: Raw string from API Gateway queryStringParameters.
        param_name: Name used in error messages.
        allowed_values: The complete list of permitted values.
        default: Return this value if value is None and no validation error.

    Returns:
        Validated value or the default.

    Raises:
        ValidationError: When value is present but not in allowed_values.
    """
    if value is None:
        return default

    if value not in allowed_values:
        raise ValidationError(
            f"Query parameter '{param_name}' must be one of: {', '.join(allowed_values)}"
        )

    return value
