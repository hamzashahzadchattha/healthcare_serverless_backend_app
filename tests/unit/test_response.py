"""Tests for the centralised HTTP response builder."""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from src.shared import response
from src.shared.exceptions import ValidationError


def test_success_default_status_code():
    result = response.success(data={"id": "123"})
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["success"] is True
    assert body["data"]["id"] == "123"
    assert "meta" not in body


def test_success_with_meta():
    result = response.success(data=[], meta={"filter": "active"})
    body = json.loads(result["body"])
    assert body["meta"]["filter"] == "active"


def test_success_custom_status_code():
    result = response.success(data={}, status_code=201)
    assert result["statusCode"] == 201


def test_error_response_shape():
    result = response.error(
        message="Not found",
        error_code="NOT_FOUND",
        status_code=404,
    )
    assert result["statusCode"] == 404
    body = json.loads(result["body"])
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Not found"


def test_error_with_details():
    result = response.error(
        message="Bad",
        error_code="ERR",
        status_code=400,
        details={"field": "email"},
    )
    body = json.loads(result["body"])
    assert body["error"]["details"]["field"] == "email"


def test_from_exception():
    exc = ValidationError("bad input", details={"field_errors": ["oops"]})
    result = response.from_exception(exc)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_json_encoder_uuid():
    uid = UUID("12345678-1234-5678-1234-567812345678")
    result = response.success(data={"id": uid})
    body = json.loads(result["body"])
    assert body["data"]["id"] == "12345678-1234-5678-1234-567812345678"


def test_json_encoder_datetime():
    dt = datetime(2025, 1, 15, 10, 30, 0)
    result = response.success(data={"ts": dt})
    body = json.loads(result["body"])
    assert body["data"]["ts"] == "2025-01-15T10:30:00"


def test_json_encoder_date():
    d = date(2025, 6, 1)
    result = response.success(data={"d": d})
    body = json.loads(result["body"])
    assert body["data"]["d"] == "2025-06-01"


def test_json_encoder_decimal():
    result = response.success(data={"amount": Decimal("19.99")})
    body = json.loads(result["body"])
    assert body["data"]["amount"] == 19.99


def test_security_headers():
    result = response.success(data={})
    headers = result["headers"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Cache-Control"] == "no-store"
    assert headers["Pragma"] == "no-cache"
