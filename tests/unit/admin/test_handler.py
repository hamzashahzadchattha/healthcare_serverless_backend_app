"""Unit tests for src/admin/handler.py."""

import importlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_testpool")

from tests.conftest import make_api_event

PATIENT_ID = str(uuid.uuid4())

MOCK_PATIENT_LIST_ROW = {
    "id": PATIENT_ID,
    "first_name": "Jane",
    "last_name": "Doe",
    "status": "active",
    "created_at": datetime(2024, 1, 15, tzinfo=timezone.utc),
    "cognito_sub": None,
}

MOCK_PATIENT_DETAIL_ROW = {
    **MOCK_PATIENT_LIST_ROW,
    "updated_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
}


def _passthrough(handler: Any) -> Any:
    """No-op decorator that returns the handler unchanged."""
    return handler


def _make_admin_event(**kwargs: Any) -> dict[str, Any]:
    """Build an API event with admin claims pre-injected."""
    event = make_api_event(**kwargs)
    event.setdefault("requestContext", {}).setdefault("authorizer", {})["claims"] = {
        "sub": str(uuid.uuid4()),
        "cognito:groups": ["admin"],
    }
    return event


def _get_handlers() -> tuple[Any, Any]:
    """Import handler module with require_admin patched to a passthrough."""
    # Remove cached module so the decorator is re-applied with the patched version
    for mod in list(sys.modules.keys()):
        if "src.admin.handler" in mod:
            del sys.modules[mod]

    with patch("src.shared.auth.require_admin", _passthrough):
        import src.admin.handler as handler_mod
        importlib.reload(handler_mod)
        return handler_mod.list_handler, handler_mod.detail_handler


class TestListHandler:
    """Tests for list_handler."""

    def test_returns_paginated_response(self) -> None:
        list_handler, _ = _get_handlers()

        mock_data = {
            "items": [MOCK_PATIENT_LIST_ROW],
            "total": 1,
            "page": 1,
            "limit": 50,
        }

        with patch("src.admin.repository.list_patients", return_value=mock_data):
            event = _make_admin_event(path="/admin/patients")
            result = list_handler(event, MagicMock(aws_request_id="req-001"))

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert len(body["data"]["items"]) == 1

    def test_respects_page_and_limit_params(self) -> None:
        list_handler, _ = _get_handlers()

        mock_data = {"items": [], "total": 0, "page": 2, "limit": 10}

        with patch("src.admin.repository.list_patients", return_value=mock_data) as mock_repo:
            event = _make_admin_event(
                path="/admin/patients",
                query_parameters={"page": "2", "limit": "10"},
            )
            list_handler(event, MagicMock(aws_request_id="req-002"))
            mock_repo.assert_called_once_with(2, 10)

    def test_unexpected_exception_returns_500(self) -> None:
        list_handler, _ = _get_handlers()

        with patch("src.admin.repository.list_patients", side_effect=Exception("DB down")):
            event = _make_admin_event(path="/admin/patients")
            result = list_handler(event, MagicMock(aws_request_id="req-003"))

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["success"] is False


class TestDetailHandler:
    """Tests for detail_handler."""

    def test_returns_patient_record(self) -> None:
        _, detail_handler = _get_handlers()

        with patch(
            "src.admin.repository.get_patient_by_id",
            return_value=MOCK_PATIENT_DETAIL_ROW,
        ):
            event = _make_admin_event(
                path=f"/admin/patients/{PATIENT_ID}",
                path_parameters={"patient_id": PATIENT_ID},
            )
            result = detail_handler(event, MagicMock(aws_request_id="req-004"))

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["data"]["id"] == PATIENT_ID

    def test_raises_not_found_for_unknown_patient(self) -> None:
        _, detail_handler = _get_handlers()

        unknown_id = str(uuid.uuid4())

        with patch("src.admin.repository.get_patient_by_id", return_value=None):
            event = _make_admin_event(
                path=f"/admin/patients/{unknown_id}",
                path_parameters={"patient_id": unknown_id},
            )
            result = detail_handler(event, MagicMock(aws_request_id="req-005"))

        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["message"] == "Patient not found"

    def test_invalid_uuid_returns_400(self) -> None:
        _, detail_handler = _get_handlers()

        event = _make_admin_event(
            path="/admin/patients/not-a-uuid",
            path_parameters={"patient_id": "not-a-uuid"},
        )
        result = detail_handler(event, MagicMock(aws_request_id="req-006"))

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"
