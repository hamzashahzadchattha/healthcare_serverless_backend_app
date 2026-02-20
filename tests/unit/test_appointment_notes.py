"""Unit tests for provider note upload -- tests service and handler separately."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_api_event

APPOINTMENT_ID = str(uuid.uuid4())
PROVIDER_ID = str(uuid.uuid4())
NOTE_ID = str(uuid.uuid4())

MOCK_APPOINTMENT_ROW = {
    "id": APPOINTMENT_ID,
    "provider_id": uuid.UUID(PROVIDER_ID),
    "status": "completed",
}

MOCK_NOTE_ROW = {
    "id": uuid.UUID(NOTE_ID),
    "created_at": datetime(2025, 8, 1, 12, 0, tzinfo=timezone.utc),
}


class TestNotesService:
    """Tests for src/appointments/notes_service.py -- no HTTP mocking."""

    def test_appointment_not_found_raises_error(self):
        from src.appointments import notes_service
        from src.appointments.models import ProviderNoteRequest
        from src.shared.exceptions import RecordNotFoundError

        payload = ProviderNoteRequest(provider_id=PROVIDER_ID, note_text="Good progress.")
        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=None,
        ):
            with pytest.raises(RecordNotFoundError):
                notes_service.upload_note(APPOINTMENT_ID, payload)

    def test_appointment_not_completed_raises_validation(self):
        from src.appointments import notes_service
        from src.appointments.models import ProviderNoteRequest
        from src.shared.exceptions import ValidationError

        appt = {**MOCK_APPOINTMENT_ROW, "status": "scheduled"}
        payload = ProviderNoteRequest(provider_id=PROVIDER_ID, note_text="Note.")
        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=appt,
        ):
            with pytest.raises(ValidationError):
                notes_service.upload_note(APPOINTMENT_ID, payload)

    def test_provider_mismatch_raises_forbidden(self):
        from src.appointments import notes_service
        from src.appointments.models import ProviderNoteRequest
        from src.shared.exceptions import ForbiddenError

        other_provider = str(uuid.uuid4())
        appt = {**MOCK_APPOINTMENT_ROW, "provider_id": uuid.UUID(other_provider)}
        payload = ProviderNoteRequest(provider_id=PROVIDER_ID, note_text="Note.")
        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=appt,
        ):
            with pytest.raises(ForbiddenError):
                notes_service.upload_note(APPOINTMENT_ID, payload)

    def test_success_returns_note_data(self):
        from src.appointments import notes_service
        from src.appointments.models import ProviderNoteRequest

        payload = ProviderNoteRequest(provider_id=PROVIDER_ID, note_text="Patient doing well.")
        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=MOCK_APPOINTMENT_ROW,
        ):
            with patch(
                "src.appointments.notes_service.repository.insert_note_with_timestamp",
                return_value=MOCK_NOTE_ROW,
            ):
                result = notes_service.upload_note(APPOINTMENT_ID, payload)
                assert result["note_id"] == NOTE_ID
                assert result["appointment_id"] == APPOINTMENT_ID


class TestNotesHandler:
    """Tests for src/appointments/handler.py notes_handler -- full event flow."""

    def test_success_returns_201(self):
        from src.appointments.handler import notes_handler

        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=MOCK_APPOINTMENT_ROW,
        ):
            with patch(
                "src.appointments.notes_service.repository.insert_note_with_timestamp",
                return_value=MOCK_NOTE_ROW,
            ):
                event = make_api_event(
                    method="POST",
                    path=f"/appointments/{APPOINTMENT_ID}/notes",
                    path_parameters={"appointment_id": APPOINTMENT_ID},
                    body={"provider_id": PROVIDER_ID, "note_text": "Patient doing well."},
                )
                result = notes_handler(event, MagicMock(aws_request_id="req-020"))
                body = json.loads(result["body"])
                assert result["statusCode"] == 201
                assert body["success"] is True
                assert "note_id" in body["data"]

    def test_appointment_not_found_returns_404(self):
        from src.appointments.handler import notes_handler

        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=None,
        ):
            event = make_api_event(
                method="POST",
                path=f"/appointments/{APPOINTMENT_ID}/notes",
                path_parameters={"appointment_id": APPOINTMENT_ID},
                body={"provider_id": PROVIDER_ID, "note_text": "Note."},
            )
            result = notes_handler(event, MagicMock(aws_request_id="req-021"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 404
            assert body["error"]["code"] == "NOT_FOUND"

    def test_provider_mismatch_returns_403(self):
        from src.appointments.handler import notes_handler

        other_provider = str(uuid.uuid4())
        appt = {**MOCK_APPOINTMENT_ROW, "provider_id": uuid.UUID(other_provider)}
        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            return_value=appt,
        ):
            event = make_api_event(
                method="POST",
                path=f"/appointments/{APPOINTMENT_ID}/notes",
                path_parameters={"appointment_id": APPOINTMENT_ID},
                body={"provider_id": PROVIDER_ID, "note_text": "Note."},
            )
            result = notes_handler(event, MagicMock(aws_request_id="req-023"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 403
            assert body["error"]["code"] == "FORBIDDEN"

    def test_unexpected_exception_returns_500(self):
        from src.appointments.handler import notes_handler

        with patch(
            "src.appointments.notes_service.repository.get_appointment_by_id",
            side_effect=Exception("Boom"),
        ):
            event = make_api_event(
                method="POST",
                path=f"/appointments/{APPOINTMENT_ID}/notes",
                path_parameters={"appointment_id": APPOINTMENT_ID},
                body={"provider_id": PROVIDER_ID, "note_text": "Note."},
            )
            result = notes_handler(event, MagicMock(aws_request_id="req-024"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 500
            assert body["success"] is False
