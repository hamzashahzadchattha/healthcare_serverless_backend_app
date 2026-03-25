"""Shared pytest fixtures for the healthcare platform test suite."""

import json
import os
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STAGE", "test")
os.environ.setdefault("REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("DB_SECRET_NAME", "healthcare-platform-test/db-credentials")
os.environ.setdefault("YOUTUBE_SECRET_NAME", "healthcare-platform-test/youtube-api-key")
os.environ.setdefault("SERVICE_NAME", "healthcare-platform-test")
os.environ.setdefault("FUNCTION_NAME", "test-function")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "healthcare-platform-test")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "HealthcarePlatform")


def make_api_event(
    method: str = "GET",
    path: str = "/",
    path_parameters: dict[str, str] | None = None,
    query_parameters: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway HTTP API v2 proxy event."""
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "requestContext": {
            "requestId": request_id or str(uuid.uuid4()),
            "http": {
                "method": method,
                "path": path,
                "sourceIp": "127.0.0.1",
            },
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": str(uuid.uuid4()),
                    },
                },
            },
        },
        "pathParameters": path_parameters or {},
        "queryStringParameters": query_parameters or {},
        "headers": headers or {"content-type": "application/json"},
        "body": json.dumps(body) if body else None,
        "isBase64Encoded": False,
    }


@pytest.fixture
def api_event_factory():
    """Return the make_api_event factory function."""
    return make_api_event


@pytest.fixture
def mock_secrets():
    """Patch Secrets Manager to return test credentials without a real AWS call."""
    with patch("src.shared.secrets._client") as mock_client:
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "host": "localhost",
                    "port": 5432,
                    "dbname": "healthcare_test",
                    "username": "test_user",
                    "password": "test_password",
                }
            ),
        }
        yield mock_client


@pytest.fixture
def mock_db(mock_secrets):
    """Patch the database module to return a mock connection."""
    with patch("src.shared.db._get_connection") as mock_get_connection:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_get_connection.return_value = mock_conn
        yield mock_get_connection, mock_conn, mock_cursor
