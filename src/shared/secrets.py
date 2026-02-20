"""AWS Secrets Manager client with in-memory caching for Lambda warm starts."""

import json
import os
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.shared.exceptions import SecretsManagerError
from src.shared.logger import get_logger


_logger = get_logger(__name__)
_client = boto3.client("secretsmanager", region_name=os.environ.get("REGION", "us-east-1"))

_cache: dict[str, dict[str, Any]] = {}


def get_secret(secret_name: str) -> dict[str, Any]:
    """Fetch and cache a secret from AWS Secrets Manager.

    Args:
        secret_name: The full secret name or ARN.

    Returns:
        Secret value parsed as a dict.

    Raises:
        SecretsManagerError: When the secret cannot be retrieved.
    """
    if secret_name in _cache:
        return _cache[secret_name]

    _logger.info("Fetching secret from Secrets Manager", secret_name=secret_name)

    try:
        response = _client.get_secret_value(SecretId=secret_name)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        raise SecretsManagerError(
            f"Failed to retrieve secret '{secret_name}'",
            details={"aws_error_code": error_code},
        ) from exc

    raw = response.get("SecretString", "{}")
    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretsManagerError(
            f"Secret '{secret_name}' is not valid JSON",
        ) from exc

    _cache[secret_name] = parsed
    return parsed


def invalidate(secret_name: str) -> None:
    """Remove a secret from the in-memory cache, forcing a fresh fetch on next access."""
    _cache.pop(secret_name, None)
    _logger.info("Secret cache invalidated", secret_name=secret_name)
