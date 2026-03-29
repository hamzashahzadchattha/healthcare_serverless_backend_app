"""Unit tests for auth-protected handlers — 401 and 403 enforcement.

Tests that require_auth raises UnauthorizedError when no token is present,
and that ownership checks raise ForbiddenError when the caller's sub does not
match the patient's cognito_sub.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_testpool")

from src.shared.exceptions import ForbiddenError, UnauthorizedError
from tests.conftest import make_api_event

PATIENT_ID = str(uuid.uuid4())
CALLER_SUB = str(uuid.uuid4())
OTHER_SUB = str(uuid.uuid4())

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


def _event_with_claims(claims: dict, path: str, path_parameters: dict, **kwargs) -> dict:
    """Build an API event with claims pre-injected at requestContext.authorizer.claims."""
    event = make_api_event(path=path, path_parameters=path_parameters, **kwargs)
    event["requestContext"]["authorizer"]["claims"] = claims
    return event


def _event_no_auth(path: str, path_parameters: dict, **kwargs) -> dict:
    """Build an API event with no Authorization header."""
    event = make_api_event(path=path, path_parameters=path_parameters, **kwargs)
    event["headers"] = {}
    return event


class TestUpcomingHandlerAuth:
    """Auth enforcement for upcoming_handler."""

    def test_missing_auth_header_raises_unauthorized(self):
        """require_auth raises UnauthorizedError when Authorization header is absent."""
        from src.appointments.handler import upcoming_handler

        event = _event_no_auth(
            path=f"/patients/{PATIENT_ID}/appointments/upcoming",
            path_parameters={"patient_id": PATIENT_ID},
        )
        with pytest.raises(UnauthorizedError):
            upcoming_handler(event, MagicMock(aws_request_id="req-auth-001"))

    def test_mismatched_sub_returns_403(self):
        """upcoming_handler returns 403 when caller sub does not match patient cognito_sub."""
        from src.appointments.handler import upcoming_handler
        import src.shared.auth as auth_module

        claims = {"sub": CALLER_SUB, "cognito:groups": []}
        fake_kid = "test-kid"
        fake_jwk = {"kid": fake_kid, "kty": "RSA"}
        fake_public_key = MagicMock()

        with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
            with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
                with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                    with patch("jwt.decode", return_value=claims):
                        with patch(
                            "src.appointments.upcoming_service.repository.get_upcoming_appointments_count",
                            return_value={"total": 0, "patient_found": 1, "cognito_sub": OTHER_SUB},
                        ):
                            with patch(
                                "src.appointments.upcoming_service.repository.get_upcoming_appointments",
                                return_value=[],
                            ):
                                event = make_api_event(
                                    path=f"/patients/{PATIENT_ID}/appointments/upcoming",
                                    path_parameters={"patient_id": PATIENT_ID},
                                    headers={"Authorization": "Bearer fake.token.here"},
                                )
                                result = upcoming_handler(event, MagicMock(aws_request_id="req-auth-002"))
                                body = json.loads(result["body"])
                                assert result["statusCode"] == 403
                                assert body["error"]["code"] == "FORBIDDEN"

    def test_matching_sub_returns_200(self):
        """upcoming_handler returns 200 when caller sub matches patient cognito_sub."""
        from src.appointments.handler import upcoming_handler
        import src.shared.auth as auth_module

        claims = {"sub": CALLER_SUB, "cognito:groups": []}
        fake_kid = "test-kid"
        fake_jwk = {"kid": fake_kid, "kty": "RSA"}
        fake_public_key = MagicMock()

        with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
            with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
                with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                    with patch("jwt.decode", return_value=claims):
                        with patch(
                            "src.appointments.upcoming_service.repository.get_upcoming_appointments_count",
                            return_value={"total": 1, "patient_found": 1, "cognito_sub": CALLER_SUB},
                        ):
                            with patch(
                                "src.appointments.upcoming_service.repository.get_upcoming_appointments",
                                return_value=[MOCK_APPOINTMENT_ROW],
                            ):
                                event = make_api_event(
                                    path=f"/patients/{PATIENT_ID}/appointments/upcoming",
                                    path_parameters={"patient_id": PATIENT_ID},
                                    headers={"Authorization": "Bearer fake.token.here"},
                                )
                                result = upcoming_handler(event, MagicMock(aws_request_id="req-auth-003"))
                                assert result["statusCode"] == 200
                                body = json.loads(result["body"])
                                # cognito_sub must not leak into the API response
                                assert "cognito_sub" not in body["data"]


class TestPrescriptionsHandlerAuth:
    """Auth enforcement for prescriptions handler."""

    def test_missing_auth_header_raises_unauthorized(self):
        """require_auth raises UnauthorizedError when Authorization header is absent."""
        from src.prescriptions.handler import handler

        event = _event_no_auth(
            path=f"/patients/{PATIENT_ID}/prescriptions",
            path_parameters={"patient_id": PATIENT_ID},
        )
        with pytest.raises(UnauthorizedError):
            handler(event, MagicMock(aws_request_id="req-auth-010"))

    def test_mismatched_sub_returns_403(self):
        """prescriptions handler returns 403 when caller sub does not match patient cognito_sub."""
        from src.prescriptions.handler import handler
        import src.shared.auth as auth_module

        claims = {"sub": CALLER_SUB, "cognito:groups": []}
        fake_kid = "test-kid"
        fake_jwk = {"kid": fake_kid, "kty": "RSA"}
        fake_public_key = MagicMock()

        with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
            with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
                with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                    with patch("jwt.decode", return_value=claims):
                        with patch(
                            "src.prescriptions.service.repository.get_prescriptions_count",
                            return_value={"total": 0, "patient_found": 1, "cognito_sub": OTHER_SUB},
                        ):
                            with patch(
                                "src.prescriptions.service.repository.get_prescriptions",
                                return_value=[],
                            ):
                                event = make_api_event(
                                    path=f"/patients/{PATIENT_ID}/prescriptions",
                                    path_parameters={"patient_id": PATIENT_ID},
                                    headers={"Authorization": "Bearer fake.token.here"},
                                )
                                result = handler(event, MagicMock(aws_request_id="req-auth-011"))
                                body = json.loads(result["body"])
                                assert result["statusCode"] == 403
                                assert body["error"]["code"] == "FORBIDDEN"

    def test_matching_sub_returns_200(self):
        """prescriptions handler returns 200 when caller sub matches patient cognito_sub."""
        from src.prescriptions.handler import handler
        import src.shared.auth as auth_module

        claims = {"sub": CALLER_SUB, "cognito:groups": []}
        fake_kid = "test-kid"
        fake_jwk = {"kid": fake_kid, "kty": "RSA"}
        fake_public_key = MagicMock()

        with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
            with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
                with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                    with patch("jwt.decode", return_value=claims):
                        with patch(
                            "src.prescriptions.service.repository.get_prescriptions_count",
                            return_value={"total": 0, "patient_found": 1, "cognito_sub": CALLER_SUB},
                        ):
                            with patch(
                                "src.prescriptions.service.repository.get_prescriptions",
                                return_value=[],
                            ):
                                event = make_api_event(
                                    path=f"/patients/{PATIENT_ID}/prescriptions",
                                    path_parameters={"patient_id": PATIENT_ID},
                                    headers={"Authorization": "Bearer fake.token.here"},
                                )
                                result = handler(event, MagicMock(aws_request_id="req-auth-012"))
                                assert result["statusCode"] == 200
                                body = json.loads(result["body"])
                                assert "cognito_sub" not in body["data"]


class TestNotesHandlerAuth:
    """Auth enforcement for notes_handler — require_auth only, no ownership check."""

    def test_missing_auth_header_raises_unauthorized(self):
        """require_auth raises UnauthorizedError when Authorization header is absent."""
        from src.appointments.handler import notes_handler

        appointment_id = str(uuid.uuid4())
        event = _event_no_auth(
            method="POST",
            path=f"/appointments/{appointment_id}/notes",
            path_parameters={"appointment_id": appointment_id},
            body={"provider_id": str(uuid.uuid4()), "note_text": "Test note"},
        )
        with pytest.raises(UnauthorizedError):
            notes_handler(event, MagicMock(aws_request_id="req-auth-020"))

    def test_any_authenticated_user_can_post_notes(self):
        """notes_handler succeeds for any authenticated caller — no ownership check."""
        from src.appointments.handler import notes_handler
        import src.shared.auth as auth_module

        appointment_id = str(uuid.uuid4())
        provider_id = str(uuid.uuid4())

        # Use a sub that does NOT match any patient — ownership is not checked
        claims = {"sub": str(uuid.uuid4()), "cognito:groups": []}
        fake_kid = "test-kid"
        fake_jwk = {"kid": fake_kid, "kty": "RSA"}
        fake_public_key = MagicMock()

        with patch.object(auth_module, "_jwks_cache", {fake_kid: fake_jwk}):
            with patch("jwt.get_unverified_header", return_value={"kid": fake_kid}):
                with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value=fake_public_key):
                    with patch("jwt.decode", return_value=claims):
                        with patch(
                            "src.appointments.notes_service.upload_note",
                            return_value={"note_id": str(uuid.uuid4()), "created_at": "2025-01-01T00:00:00"},
                        ):
                            event = make_api_event(
                                method="POST",
                                path=f"/appointments/{appointment_id}/notes",
                                path_parameters={"appointment_id": appointment_id},
                                body={"provider_id": provider_id, "note_text": "Provider observation"},
                                headers={"Authorization": "Bearer fake.token.here"},
                            )
                            result = notes_handler(event, MagicMock(aws_request_id="req-auth-021"))
                            assert result["statusCode"] == 201
