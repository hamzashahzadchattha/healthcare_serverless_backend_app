"""AWS Secrets Manager parameter fetching via Powertools Parameters.

Replaces the custom secrets.py module. Uses a 300-second TTL cache with
automatic force-refresh support for secret rotation scenarios.

Usage:
    from src.shared.parameters import get_db_credentials, get_youtube_api_key
"""

import os
from typing import Any

from aws_lambda_powertools.utilities import parameters


def get_secret(secret_name: str, *, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch and parse a JSON secret from Secrets Manager.

    Args:
        secret_name: The secret ARN or name.
        force_refresh: Bypass the cache and force a fresh fetch.
                       Call with True after a DatabaseConnectionError caused
                       by stale credentials (e.g. after RDS password rotation).

    Returns:
        Parsed JSON dict from the secret value.
    """
    raw = parameters.get_secret(
        name=secret_name,
        transform="json",          # Parses the JSON secret string automatically
        max_age=300,               # 5-minute TTL — safe across RDS rotation window
        force_fetch=force_refresh,
    )
    return raw  # type: ignore[return-value]


def get_db_credentials(*, force_refresh: bool = False) -> dict[str, Any]:
    """Convenience wrapper for the RDS managed user secret."""
    return get_secret(os.environ["DB_SECRET_NAME"], force_refresh=force_refresh)


def get_youtube_api_key(*, force_refresh: bool = False) -> str:
    """Convenience wrapper for the YouTube API key secret."""
    secret = get_secret(os.environ["YOUTUBE_SECRET_NAME"], force_refresh=force_refresh)
    return secret["api_key"]
