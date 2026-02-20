"""Unit tests for prescription listing -- tests service and handler separately."""

import json
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_api_event


PATIENT_ID = str(uuid.uuid4())

MOCK_PRESCRIPTION_ROW = {
    "prescription_id": uuid.uuid4(),
    "medication_name": "Metformin",
    "dosage": "500mg",
    "frequency": "Twice daily",
    "start_date": date(2025, 1, 1),
    "end_date": None,
    "status": "active",
    "provider_id": uuid.uuid4(),
    "provider_first_name": "Sarah",
    "provider_last_name": "Smith",
}


class TestPrescriptionService:
    """Tests for src/prescriptions/service.py -- no HTTP mocking."""

    def test_patient_not_found_raises_error(self):
        from src.prescriptions import service
        from src.shared.exceptions import RecordNotFoundError

        with patch("src.prescriptions.service.repository.patient_exists", return_value=False):
            with pytest.raises(RecordNotFoundError):
                service.list_prescriptions(PATIENT_ID, "active")

    def test_success_returns_formatted_prescriptions(self):
        from src.prescriptions import service

        with patch("src.prescriptions.service.repository.patient_exists", return_value=True):
            with patch(
                "src.prescriptions.service.repository.get_prescriptions",
                return_value=[MOCK_PRESCRIPTION_ROW],
            ):
                result = service.list_prescriptions(PATIENT_ID, "active")
                assert result["total"] == 1
                rx = result["prescriptions"][0]
                assert rx["medication_name"] == "Metformin"
                assert "Dr." in rx["prescribed_by"]["full_name"]

    def test_empty_list_for_no_prescriptions(self):
        from src.prescriptions import service

        with patch("src.prescriptions.service.repository.patient_exists", return_value=True):
            with patch(
                "src.prescriptions.service.repository.get_prescriptions",
                return_value=[],
            ):
                result = service.list_prescriptions(PATIENT_ID, "all")
                assert result["total"] == 0
                assert result["prescriptions"] == []


class TestPrescriptionHandler:
    """Tests for src/prescriptions/handler.py -- full event-to-response flow."""

    def test_success_returns_200(self):
        from src.prescriptions.handler import handler

        with patch("src.prescriptions.service.repository.patient_exists", return_value=True):
            with patch(
                "src.prescriptions.service.repository.get_prescriptions",
                return_value=[MOCK_PRESCRIPTION_ROW],
            ):
                event = make_api_event(
                    path=f"/patients/{PATIENT_ID}/prescriptions",
                    path_parameters={"patient_id": PATIENT_ID},
                    query_parameters={"filter": "active"},
                )
                result = handler(event, MagicMock(aws_request_id="req-030"))
                body = json.loads(result["body"])
                assert result["statusCode"] == 200
                assert body["success"] is True
                assert body["data"]["total"] == 1
                assert body["meta"]["filter"] == "active"

    def test_patient_not_found_returns_404(self):
        from src.prescriptions.handler import handler

        with patch("src.prescriptions.service.repository.patient_exists", return_value=False):
            event = make_api_event(
                path=f"/patients/{PATIENT_ID}/prescriptions",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = handler(event, MagicMock(aws_request_id="req-031"))
            assert result["statusCode"] == 404

    def test_invalid_filter_returns_400(self):
        from src.prescriptions.handler import handler

        event = make_api_event(
            path=f"/patients/{PATIENT_ID}/prescriptions",
            path_parameters={"patient_id": PATIENT_ID},
            query_parameters={"filter": "invalid_value"},
        )
        result = handler(event, MagicMock(aws_request_id="req-032"))
        body = json.loads(result["body"])
        assert result["statusCode"] == 400
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_unexpected_exception_returns_500(self):
        from src.prescriptions.handler import handler

        with patch(
            "src.prescriptions.service.repository.patient_exists",
            side_effect=Exception("Fail"),
        ):
            event = make_api_event(
                path=f"/patients/{PATIENT_ID}/prescriptions",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = handler(event, MagicMock(aws_request_id="req-033"))
            body = json.loads(result["body"])
            assert result["statusCode"] == 500
            assert body["success"] is False
