"""POST /appointments/{appointment_id}/notes — uploads a post-appointment provider note."""

import time
from typing import Any

from src.shared import db, response
from src.shared.exceptions import (
    ForbiddenError,
    HealthcarePlatformError,
    RecordNotFoundError,
    ValidationError,
)
from src.shared.logger import get_logger
from src.shared.request_validator import validate_body, validate_uuid_path_param


_logger = get_logger(__name__)

_NOTE_BODY_SCHEMA: dict = {
    "type": "object",
    "required": ["provider_id", "note_text"],
    "additionalProperties": False,
    "properties": {
        "provider_id": {"type": "string"},
        "note_text": {"type": "string", "minLength": 1, "maxLength": 10000},
    },
}

_SELECT_APPOINTMENT = """
    SELECT id, provider_id, status FROM appointments WHERE id = %s
"""

# Both operations run inside a single transaction for atomicity
_INSERT_NOTE = """
    INSERT INTO appointment_notes (appointment_id, provider_id, note_text)
    VALUES (%s, %s, %s)
"""

_UPDATE_APPOINTMENT_TIMESTAMP = """
    UPDATE appointments SET updated_at = NOW() WHERE id = %s
"""

# Fetched after transaction to get the created note's id and timestamp
_SELECT_LATEST_NOTE = """
    SELECT id, created_at
    FROM appointment_notes
    WHERE appointment_id = %s AND provider_id = %s
    ORDER BY created_at DESC
    LIMIT 1
"""


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for POST /appointments/{appointment_id}/notes."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()

    path_params = event.get("pathParameters") or {}
    _logger.info("Provider note upload request received")

    try:
        appointment_id = validate_uuid_path_param(
            path_params.get("appointment_id"),
            "appointment_id",
        )
        body = validate_body(event.get("body"), _NOTE_BODY_SCHEMA)
        provider_id = validate_uuid_path_param(body.get("provider_id"), "provider_id")

        appt_rows = db.execute_query(_SELECT_APPOINTMENT, (appointment_id,))
        if not appt_rows:
            raise RecordNotFoundError("Appointment not found")

        appt = appt_rows[0]

        if appt["status"] != "completed":
            raise ValidationError("Notes can only be added to completed appointments")

        if str(appt["provider_id"]) != provider_id:
            raise ForbiddenError(
                "Provider is not authorised to add notes to this appointment",
            )

        # Atomic: insert note + update appointment timestamp in one transaction
        db.execute_transaction(
            [
                (_INSERT_NOTE, (appointment_id, provider_id, body["note_text"])),
                (_UPDATE_APPOINTMENT_TIMESTAMP, (appointment_id,)),
            ]
        )

        note_rows = db.execute_query(
            _SELECT_LATEST_NOTE,
            (appointment_id, provider_id),
            commit=False,
        )
        note = note_rows[0]

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Provider note created",
            appointment_id=appointment_id,
            note_id=str(note["id"]),
            duration_ms=elapsed_ms,
        )

        return response.success(
            data={
                "note_id": str(note["id"]),
                "appointment_id": appointment_id,
                "created_at": note["created_at"].isoformat(),
            },
            status_code=201,
        )

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Provider note upload failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error uploading provider note",
            duration_ms=elapsed_ms,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
