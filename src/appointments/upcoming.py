"""GET /patients/{patient_id}/appointments/upcoming — returns upcoming scheduled appointments."""

import time
from typing import Any

from src.shared import db, response
from src.shared.exceptions import HealthcarePlatformError, RecordNotFoundError
from src.shared.logger import get_logger
from src.shared.request_validator import validate_uuid_path_param


_logger = get_logger(__name__)

_CHECK_PATIENT_EXISTS = "SELECT id FROM patients WHERE id = %s AND status = 'active'"

_SELECT_UPCOMING = """
    SELECT
        a.id                AS appointment_id,
        p.id                AS provider_id,
        p.first_name        AS provider_first_name,
        p.last_name         AS provider_last_name,
        p.specialty         AS provider_specialty,
        a.scheduled_at,
        a.duration_minutes,
        a.appointment_type,
        a.status
    FROM appointments a
    JOIN providers p ON p.id = a.provider_id
    WHERE a.patient_id = %s
      AND a.status = 'scheduled'
      AND a.scheduled_at >= NOW()
    ORDER BY a.scheduled_at ASC
"""


def _format_appointment(row: dict[str, Any]) -> dict[str, Any]:
    """Transform a flat DB row into the nested appointment response shape."""
    return {
        "appointment_id": str(row["appointment_id"]),
        "provider": {
            "provider_id": str(row["provider_id"]),
            "full_name": f"Dr. {row['provider_first_name']} {row['provider_last_name']}",
            "specialty": row["provider_specialty"],
        },
        "scheduled_at": row["scheduled_at"].isoformat(),
        "duration_minutes": row["duration_minutes"],
        "appointment_type": row["appointment_type"],
        "status": row["status"],
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for GET /patients/{patient_id}/appointments/upcoming."""
    _logger.set_request_id(context.aws_request_id)
    start = time.perf_counter()

    path_params = event.get("pathParameters") or {}
    _logger.info("Upcoming appointments request received")

    try:
        patient_id = validate_uuid_path_param(path_params.get("patient_id"), "patient_id")

        patient_rows = db.execute_query(_CHECK_PATIENT_EXISTS, (patient_id,))
        if not patient_rows:
            raise RecordNotFoundError("Patient not found")

        appt_rows = db.execute_query(_SELECT_UPCOMING, (patient_id,))
        appointments = [_format_appointment(row) for row in appt_rows]

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info(
            "Upcoming appointments retrieved",
            patient_id=patient_id,
            count=len(appointments),
            duration_ms=elapsed_ms,
        )

        return response.success(
            data={"appointments": appointments, "total": len(appointments)},
        )

    except HealthcarePlatformError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.warning(
            "Upcoming appointments request failed",
            error_code=exc.error_code,
            duration_ms=elapsed_ms,
        )
        return response.from_exception(exc)

    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.error(
            "Unexpected error retrieving upcoming appointments",
            duration_ms=elapsed_ms,
        )
        return response.error(
            message="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
