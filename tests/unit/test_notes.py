"""Unit tests for POST /appointments/{appointment_id}/notes."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_api_event


APPOINTMENT_ID = str(uuid.uuid4())
PROVIDER_ID = str(uuid.uuid4())
NOTE_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _mock_db_module(mock_db):
    _, mock_conn, mock_cursor = mock_db
    mock_cursor.fetchall.side_effect = [
        [{"id": APPOINTMENT_ID, "provider_id": uuid.UUID(PROVIDER_ID), "status": "completed"}],
        [
            {
                "id": uuid.UUID(NOTE_ID),
                "created_at": datetime(2025, 8, 1, 12, 0, tzinfo=timezone.utc),
            }
        ],
    ]
    mock_cursor.description = None
    return mock_cursor


def test_notes_success(_mock_db_module):
    from src.appointments.notes import handler

    event = make_api_event(
        method="POST",
        path=f"/appointments/{APPOINTMENT_ID}/notes",
        path_parameters={"appointment_id": APPOINTMENT_ID},
        body={"provider_id": PROVIDER_ID, "note_text": "Patient doing well."},
    )
    result = handler(event, MagicMock(aws_request_id="req-020"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 201
    assert body["success"] is True
    assert "note_id" in body["data"]


def test_notes_appointment_not_found(_mock_db_module):
    from src.appointments.notes import handler

    _mock_db_module.fetchall.side_effect = [
        [],
    ]
    event = make_api_event(
        method="POST",
        path=f"/appointments/{APPOINTMENT_ID}/notes",
        path_parameters={"appointment_id": APPOINTMENT_ID},
        body={"provider_id": PROVIDER_ID, "note_text": "Note."},
    )
    result = handler(event, MagicMock(aws_request_id="req-021"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 404
    assert body["error"]["code"] == "NOT_FOUND"


def test_notes_appointment_not_completed(_mock_db_module):
    from src.appointments.notes import handler

    _mock_db_module.fetchall.side_effect = [
        [{"id": APPOINTMENT_ID, "provider_id": uuid.UUID(PROVIDER_ID), "status": "scheduled"}],
    ]
    event = make_api_event(
        method="POST",
        path=f"/appointments/{APPOINTMENT_ID}/notes",
        path_parameters={"appointment_id": APPOINTMENT_ID},
        body={"provider_id": PROVIDER_ID, "note_text": "Note."},
    )
    result = handler(event, MagicMock(aws_request_id="req-022"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_notes_provider_mismatch(_mock_db_module):
    from src.appointments.notes import handler

    other_provider = str(uuid.uuid4())
    _mock_db_module.fetchall.side_effect = [
        [{"id": APPOINTMENT_ID, "provider_id": uuid.UUID(other_provider), "status": "completed"}],
    ]
    event = make_api_event(
        method="POST",
        path=f"/appointments/{APPOINTMENT_ID}/notes",
        path_parameters={"appointment_id": APPOINTMENT_ID},
        body={"provider_id": PROVIDER_ID, "note_text": "Note."},
    )
    result = handler(event, MagicMock(aws_request_id="req-023"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 403
    assert body["error"]["code"] == "FORBIDDEN"


def test_notes_unexpected_exception(_mock_db_module):
    from src.appointments.notes import handler

    _mock_db_module.fetchall.side_effect = Exception("Boom")
    event = make_api_event(
        method="POST",
        path=f"/appointments/{APPOINTMENT_ID}/notes",
        path_parameters={"appointment_id": APPOINTMENT_ID},
        body={"provider_id": PROVIDER_ID, "note_text": "Note."},
    )
    result = handler(event, MagicMock(aws_request_id="req-024"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 500
    assert body["success"] is False
