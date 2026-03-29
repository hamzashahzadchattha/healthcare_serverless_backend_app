"""Shared Cognito utilities and client initialization for Auth handlers."""

import json
import os
from typing import Any

import boto3

from src.shared.exceptions import ValidationError

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
        raise ValidationError(
            "Missing required fields",
            details={"missing": missing},
        )
