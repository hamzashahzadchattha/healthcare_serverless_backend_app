"""Unit tests for upcoming appointments -- tests service and handler separately."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_api_event


PATIENT_ID = str(uuid.uuid4())

MOCK_APPOINTMENT_ROW = {
    "appointment_id": uuid.uuid4(),
    "provider_id": uuid.uuid4(),
    "provider_first_name": "Jane",
    "provider_last_name": "Smith",
    "provider_specialty": "Cardiology",
    "scheduled_at": datetime(2025, 9, 1, 14, 0, tzinfo=timezone.utc),
    "duration_minutes": 30,
    "appointment_type": "in_person",
    "status": "scheduled",
}


class TestUpcomingService:
    """Tests for src/appointments/upcoming_service.py -- no HTTP mocking."""

    def test_patient_not_found_raises_error(self):
        from src.appointments import upcoming_service
        from src.shared.exceptions import RecordNotFoundError

        with patch(
            "src.appointments.upcoming_service.repository.patient_exists",
            return_value=False,
        ):
            with pytest.raises(RecordNotFoundError):
                upcoming_service.get_upcoming_appointments(PATIENT_ID)

    def test_success_returns_formatted_appointments(self):
        from src.appointments import upcoming_service

        with patch(
            "src.appointments.upcoming_service.repository.patient_exists",
            return_value=True,
        ):
            with patch(
                "src.appointments.upcoming_service.repository.get_upcoming_appointments",
                return_value=[MOCK_APPOINTMENT_ROW],
            ):
                result = upcoming_service.get_upcoming_appointments(PATIENT_ID)
                assert result["total"] == 1
                appt = result["appointments"][0]
                assert appt["provider"]["specialty"] == "Cardiology"
                assert "Dr." in appt["provider"]["full_name"]

    def test_empty_list_for_no_appointments(self):
        from src.appointments import upcoming_service

        with patch(
            "src.appointments.upcoming_service.repository.patient_exists",
            return_value=True,
        ):
            with patch(
                "src.appointments.upcoming_service.repository.get_upcoming_appointments",
                return_value=[],
            ):
                result = upcoming_service.get_upcoming_appointments(PATIENT_ID)
                assert result["total"] == 0
                assert result["appointments"] == []


class TestUpcomingHandler:
    """Tests for src/appointments/handler.py upcoming_handler -- full event flow."""

    def test_success_returns_200(self):
        from src.appointments.handler import upcoming_handler

        with patch(
            "src.appointments.upcoming_service.repository.patient_exists",
            return_value=True,
        ):
            with patch(
                "src.appointments.upcoming_service.repository.get_upcoming_appointments",
                return_value=[MOCK_APPOINTMENT_ROW],
            ):
                event = make_api_event(
                    path=f"/patients/{PATIENT_ID}/appointments/upcoming",
                    path_parameters={"patient_id": PATIENT_ID},
                )
                result = upcoming_handler(event, MagicMock(aws_request_id="req-010"))
                body = json.loads(result["body"])
                assert result["statusCode"] == 200
                assert body["success"] is True
                assert body["data"]["total"] == 1
                assert body["data"]["appointments"][0]["provider"]["specialty"] == "Cardiology"

    def test_invalid_uuid_returns_400(self):
        from src.appointments.handler import upcoming_handler

        event = make_api_event(
            path="/patients/bad-uuid/appointments/upcoming",
            path_parameters={"patient_id": "bad-uuid"},
        )
        result = upcoming_handler(event, MagicMock(aws_request_id="req-011"))
        body = json.loads(result["body"])
        assert result["statusCode"] == 400
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_patient_not_found_returns_404(self):
        from src.appointments.handler import upcoming_handler

        with patch(
            "src.appointments.upcoming_service.repository.patient_exists",
            return_value=False,
        ):
            event = make_api_event(
                path=f"/patients/{PATIENT_ID}/appointments/upcoming",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = upcoming_handler(event, MagicMock(aws_request_id="req-012"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 404
            assert body["error"]["code"] == "NOT_FOUND"

    def test_unexpected_exception_returns_500(self):
        from src.appointments.handler import upcoming_handler

        with patch(
            "src.appointments.upcoming_service.repository.patient_exists",
            side_effect=Exception("DB down"),
        ):
            event = make_api_event(
                path=f"/patients/{PATIENT_ID}/appointments/upcoming",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = upcoming_handler(event, MagicMock(aws_request_id="req-013"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 500
            assert body["success"] is False
