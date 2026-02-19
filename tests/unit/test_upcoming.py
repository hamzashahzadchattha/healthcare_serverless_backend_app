"""Unit tests for GET /patients/{patient_id}/appointments/upcoming."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_api_event


PATIENT_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _mock_db_module(mock_db):
    _, mock_conn, mock_cursor = mock_db
    mock_cursor.fetchall.side_effect = [
        [{"id": PATIENT_ID}],
        [
            {
                "appointment_id": uuid.uuid4(),
                "provider_id": uuid.uuid4(),
                "provider_first_name": "Jane",
                "provider_last_name": "Smith",
                "provider_specialty": "Cardiology",
                "scheduled_at": datetime(2025, 9, 1, 14, 0, tzinfo=timezone.utc),
                "duration_minutes": 30,
                "appointment_type": "in_person",
                "status": "scheduled",
            },
        ],
    ]
    return mock_cursor


def test_upcoming_success(_mock_db_module):
    from src.appointments.upcoming import handler

    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/appointments/upcoming",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-010"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["appointments"][0]["provider"]["specialty"] == "Cardiology"


def test_upcoming_invalid_uuid():
    from src.appointments.upcoming import handler

    event = make_api_event(
        path="/patients/bad-uuid/appointments/upcoming",
        path_parameters={"patient_id": "bad-uuid"},
    )
    result = handler(event, MagicMock(aws_request_id="req-011"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_upcoming_patient_not_found(_mock_db_module):
    from src.appointments.upcoming import handler

    _mock_db_module.fetchall.side_effect = [
        [],
    ]
    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/appointments/upcoming",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-012"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 404
    assert body["error"]["code"] == "NOT_FOUND"


def test_upcoming_unexpected_exception(_mock_db_module):
    from src.appointments.upcoming import handler

    _mock_db_module.fetchall.side_effect = Exception("DB down")
    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/appointments/upcoming",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-013"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 500
    assert body["success"] is False
