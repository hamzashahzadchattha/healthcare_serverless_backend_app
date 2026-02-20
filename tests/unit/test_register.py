"""Unit tests for patient registration -- tests service and handler separately."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_api_event


VALID_BODY = {
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1985-06-15",
    "email": "john.doe@example.com",
    "phone": "+12025551234",
}


class TestRegisterPatientService:
    """Tests for src/patients/service.py -- called directly, no HTTP mocking."""

    def test_duplicate_email_raises_error(self):
        from src.patients import service
        from src.patients.models import PatientRegistrationRequest
        from src.shared.exceptions import DuplicateRecordError

        payload = PatientRegistrationRequest(**VALID_BODY)
        with patch("src.patients.service.repository.find_by_email_sha256") as mock_find:
            mock_find.return_value = [{"id": str(uuid.uuid4())}]
            with pytest.raises(DuplicateRecordError):
                service.register_patient(payload)

    def test_successful_registration_calls_insert(self):
        from src.patients import service
        from src.patients.models import PatientRegistrationRequest

        payload = PatientRegistrationRequest(**VALID_BODY)
        mock_row = {"id": uuid.uuid4(), "status": "active"}

        with patch("src.patients.service.repository.find_by_email_sha256", return_value=[]):
            with patch("src.patients.service.repository.insert_patient", return_value=mock_row):
                result = service.register_patient(payload)
                assert result.status == "active"
                assert result.patient_id == str(mock_row["id"])


class TestRegisterHandler:
    """Tests for src/patients/handler.py -- full event-to-response flow."""

    def test_success_returns_201(self):
        from src.patients.handler import handler

        mock_row = {"id": uuid.uuid4(), "status": "active"}

        with patch("src.patients.service.repository.find_by_email_sha256", return_value=[]):
            with patch("src.patients.service.repository.insert_patient", return_value=mock_row):
                event = make_api_event(method="POST", path="/patients/register", body=VALID_BODY)
                result = handler(event, MagicMock(aws_request_id="req-001"))
                body = json.loads(result["body"])
                assert result["statusCode"] == 201
                assert body["success"] is True
                assert "patient_id" in body["data"]

    def test_missing_field_returns_400(self):
        from src.patients.handler import handler

        bad_body = {k: v for k, v in VALID_BODY.items() if k != "email"}
        event = make_api_event(method="POST", path="/patients/register", body=bad_body)
        result = handler(event, MagicMock(aws_request_id="req-002"))
        body = json.loads(result["body"])
        assert result["statusCode"] == 400
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_future_dob_returns_400(self):
        from src.patients.handler import handler

        bad_body = {**VALID_BODY, "dob": "2099-01-01"}
        event = make_api_event(method="POST", path="/patients/register", body=bad_body)
        result = handler(event, MagicMock(aws_request_id="req-003"))
        assert json.loads(result["body"])["error"]["code"] == "VALIDATION_ERROR"

    def test_unexpected_exception_returns_500(self):
        from src.patients.handler import handler

        with patch(
            "src.patients.service.repository.find_by_email_sha256",
            side_effect=Exception("boom"),
        ):
            event = make_api_event(method="POST", path="/patients/register", body=VALID_BODY)
            result = handler(event, MagicMock(aws_request_id="req-004"))
            assert result["statusCode"] == 500
            assert "boom" not in result["body"]
