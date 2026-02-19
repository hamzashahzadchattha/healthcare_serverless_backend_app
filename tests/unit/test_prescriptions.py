"""Unit tests for GET /patients/{patient_id}/prescriptions."""

import json
import uuid
from datetime import date
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
            },
        ],
    ]
    return mock_cursor


def test_prescriptions_success(_mock_db_module):
    from src.prescriptions.list_prescriptions import handler

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
    rx = body["data"]["prescriptions"][0]
    assert rx["medication_name"] == "Metformin"


def test_prescriptions_patient_not_found(_mock_db_module):
    from src.prescriptions.list_prescriptions import handler

    _mock_db_module.fetchall.side_effect = [
        [],
    ]
    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/prescriptions",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-031"))
    assert result["statusCode"] == 404


def test_prescriptions_invalid_filter():
    from src.prescriptions.list_prescriptions import handler

    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/prescriptions",
        path_parameters={"patient_id": PATIENT_ID},
        query_parameters={"filter": "invalid_value"},
    )
    result = handler(event, MagicMock(aws_request_id="req-032"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_prescriptions_unexpected_exception(_mock_db_module):
    from src.prescriptions.list_prescriptions import handler

    _mock_db_module.fetchall.side_effect = Exception("Fail")
    event = make_api_event(
        path=f"/patients/{PATIENT_ID}/prescriptions",
        path_parameters={"patient_id": PATIENT_ID},
    )
    result = handler(event, MagicMock(aws_request_id="req-033"))
    body = json.loads(result["body"])
    assert result["statusCode"] == 500
    assert body["success"] is False
