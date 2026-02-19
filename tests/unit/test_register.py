"""Unit tests for POST /patients/register."""

import json
import uuid
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_api_event


VALID_BODY = {
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1985-06-15",
    "email": "john.doe@example.com",
    "phone": "+12025551234",
}


@pytest.fixture(autouse=True)
def _mock_db_module(mock_db):
    _, mock_conn, mock_cursor = mock_db
    mock_cursor.fetchall.side_effect = [
        [],
        [{"id": uuid.uuid4(), "status": "active"}],
    ]
    return mock_cursor


def test_register_success(_mock_db_module):
    from src.patients.register import handler

    event = make_api_event(method="POST", path="/patients/register", body=VALID_BODY)
    result = handler(event, MagicMock(aws_request_id="req-001"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 201
    assert body["success"] is True
    assert "patient_id" in body["data"]
    assert body["data"]["status"] == "active"


def test_register_missing_required_field():
    from src.patients.register import handler

    incomplete = {k: v for k, v in VALID_BODY.items() if k != "email"}
    event = make_api_event(method="POST", path="/patients/register", body=incomplete)
    result = handler(event, MagicMock(aws_request_id="req-002"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_register_future_dob():
    from src.patients.register import handler

    event = make_api_event(
        method="POST",
        path="/patients/register",
        body={**VALID_BODY, "dob": "2099-01-01"},
    )
    result = handler(event, MagicMock(aws_request_id="req-003"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_register_duplicate_email(_mock_db_module):
    from src.patients.register import handler

    _mock_db_module.fetchall.side_effect = [
        [{"id": uuid.uuid4()}],
    ]
    event = make_api_event(method="POST", path="/patients/register", body=VALID_BODY)
    result = handler(event, MagicMock(aws_request_id="req-004"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 409
    assert body["error"]["code"] == "DUPLICATE_RECORD"


def test_register_unexpected_exception(_mock_db_module):
    from src.patients.register import handler

    _mock_db_module.fetchall.side_effect = Exception("Unexpected boom")
    event = make_api_event(method="POST", path="/patients/register", body=VALID_BODY)
    result = handler(event, MagicMock(aws_request_id="req-005"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 500
    assert body["success"] is False
    assert "Unexpected boom" not in result["body"]
