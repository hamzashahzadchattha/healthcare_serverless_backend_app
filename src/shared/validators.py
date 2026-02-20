"""Pydantic-aware input validation for Lambda event payloads.

Provides typed parse functions that construct Pydantic models from raw
API Gateway event data, raising the application's ValidationError on failure.
"""

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from src.shared.exceptions import ValidationError


T = TypeVar("T", bound=BaseModel)

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def parse_body(body_raw: str | None, model_class: type[T]) -> T:
    """Parse a JSON string and validate it against a Pydantic model.

    Args:
        body_raw: Raw JSON string from the API Gateway event body.
        model_class: The Pydantic BaseModel subclass to construct.

    Returns:
        An instance of model_class populated with validated data.

    Raises:
        ValidationError: When the body is missing, not valid JSON,
            or fails Pydantic validation.
    """
    if not body_raw:
        raise ValidationError("Request body is required")

    try:
        data: dict[str, Any] = json.loads(body_raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Request body must be valid JSON") from exc

    try:
        return model_class.model_validate(data)
    except PydanticValidationError as exc:
        messages = [
            f"Field '{'.'.join(str(loc) for loc in err['loc'])}': {err['msg']}"
            for err in exc.errors()
        ]
        raise ValidationError(
            "Request body validation failed",
            details={"field_errors": messages},
        ) from exc


def parse_uuid_param(value: str | None, param_name: str) -> str:
    """Validate that a path parameter is a valid UUID.

    Args:
        value: Raw string value from the API Gateway event path parameters.
        param_name: Name of the parameter (used only in error messages).

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


def parse_enum_param(
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
        default: Return this value if value is None.

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
